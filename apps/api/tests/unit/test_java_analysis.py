"""Java / Spring understanding on a synthetic Spring Modulith codebase (no real app): modules and boundaries, routes,
listeners, effects through injected collaborators, Redis channel patterns, websocket and scheduled entry points, flows."""
import uuid
from datetime import UTC, datetime
from pathlib import Path

from archtwin.architecture import builder, flows
from archtwin.connectors.analyzers import java_code
from archtwin.connectors.analyzers.repo import analyze_repository

J = "app/src/main/java/com/acme/"
FILES = {
    "compose.yaml": ("services:\n  db: {image: 'postgres:17'}\n  cache: {image: 'valkey/valkey:8'}\n"
                     "  app:\n    build: ./app\n    environment:\n      SPRING_DATASOURCE_URL: jdbc:postgresql://db:5432/app\n"
                     "      CACHE_HOST: cache\n      HEALTH_URL: http://db:5432/healthz\n"),
    "app/Dockerfile": "FROM eclipse-temurin:21\n",
    "app/src/main/resources/db/migration/V1__init.sql": (
        "CREATE TABLE orders (id uuid PRIMARY KEY, customer_id uuid NOT NULL REFERENCES customers(id), total numeric);\n"
        "CREATE TABLE customers (id uuid PRIMARY KEY, name text NOT NULL);\n"
        "CREATE TABLE outbox (id bigserial PRIMARY KEY, payload jsonb);\n"),
    J + "ShopApplication.java": "package com.acme;\n@SpringBootApplication\npublic class ShopApplication {}\n",
    J + "orders/package-info.java": '@org.springframework.modulith.ApplicationModule(displayName = "Orders", allowedDependencies = {"customers"})\npackage com.acme.orders;\n',
    J + "orders/OrderPlaced.java": "package com.acme.orders;\npublic record OrderPlaced(String id) {}\n",
    J + "orders/OrderController.java": """package com.acme.orders;
import com.acme.orders.internal.OrderService;
@RestController
@RequestMapping("/api/orders")
class OrderController {
    private final OrderService service;
    OrderController(OrderService service) { this.service = service; }
    @PostMapping
    String place(String body) { return service.place(body); }
    @GetMapping("/{id}")
    String get(String id) { return service.find(id); }
}
""",
    J + "orders/internal/OrderService.java": """package com.acme.orders.internal;
import com.acme.orders.OrderPlaced;
import com.acme.customers.CustomerApi;
@Service
public class OrderService {
    private final JdbcClient jdbc;
    private final ApplicationEventPublisher events;
    private final CustomerApi customers;
    public OrderService(JdbcClient jdbc, ApplicationEventPublisher events, CustomerApi customers) {
        this.jdbc = jdbc; this.events = events; this.customers = customers;
    }
    public String place(String body) {
        customers.check(body);
        jdbc.sql(\"\"\"
            INSERT INTO orders (id, customer_id, total) VALUES (:id, :c, :t)
            \"\"\").update();
        events.publishEvent(new com.acme.orders.OrderPlaced(body));
        return body;
    }
    public String find(String id) { return jdbc.sql("SELECT * FROM orders WHERE id = :id").query(String.class).single(); }
}
""",
    J + "customers/package-info.java": '@org.springframework.modulith.ApplicationModule(displayName = "Customers")\npackage com.acme.customers;\n',
    J + "customers/CustomerApi.java": "package com.acme.customers;\npublic interface CustomerApi { void check(String id); }\n",
    J + "customers/internal/CustomerRepo.java": """package com.acme.customers.internal;
import com.acme.customers.CustomerApi;
@Repository
class CustomerRepo implements CustomerApi {
    private final JdbcTemplate jdbc;
    CustomerRepo(JdbcTemplate jdbc) { this.jdbc = jdbc; }
    public void check(String id) { jdbc.queryForObject("select count(*) from customers where id = ?", Long.class, id); }
}
""",
    J + "notify/package-info.java": '@org.springframework.modulith.ApplicationModule(displayName = "Notifications")\npackage com.acme.notify;\n',
    J + "notify/Hints.java": """package com.acme.notify;
@Component
public class Hints {
    static final String PREFIX = "order:";
    private final StringRedisTemplate redis;
    Hints(StringRedisTemplate redis) { this.redis = redis; }
    public void signal(String id) { publish(PREFIX + id, "x"); }
    private void publish(String channel, String body) { redis.convertAndSend(channel, body); }
}
""",
    J + "notify/OrderListener.java": """package com.acme.notify;
import com.acme.orders.OrderPlaced;
import com.acme.orders.internal.OrderService;
@Component
class OrderListener {
    private final Hints hints;
    private final OrderService leaked;
    OrderListener(Hints hints, OrderService leaked) { this.hints = hints; this.leaked = leaked; }
    @ApplicationModuleListener
    void on(OrderPlaced event) { hints.signal(event.id()); jdbcOutbox(); }
    private void jdbcOutbox() {}
    @Scheduled(fixedDelayString = "PT5S")
    void drain() {}
}
""",
    J + "notify/WsConfig.java": """package com.acme.notify;
@Configuration
class WsConfig implements WebSocketConfigurer {
    static final String PATH = "/ws";
    private final Socket handler;
    WsConfig(Socket handler) { this.handler = handler; }
    public void registerWebSocketHandlers(WebSocketHandlerRegistry registry) { registry.addHandler(handler, PATH); }
    RedisMessageListenerContainer container(MessageListener l) {
        RedisMessageListenerContainer c = new RedisMessageListenerContainer();
        c.addMessageListener(l, new PatternTopic(Hints.PREFIX + "*"));
        return c;
    }
}
""",
    J + "notify/Socket.java": "package com.acme.notify;\n@Component\nclass Socket extends TextWebSocketHandler {}\n",
    "app/src/test/java/com/acme/FakeTest.java": "package com.acme;\n@RestController\nclass FakeTest { @GetMapping(\"/never\") void x() {} }\n",
}


def _repo(tmp_path: Path) -> Path:
    for rel, body in FILES.items():
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(body)
    return tmp_path


def test_model_modules_boundaries_routes_listeners(tmp_path: Path):
    root = _repo(tmp_path) / "app"
    cb = java_code.analyze(root, list(root.rglob("*.java")), lambda f: f.read_bytes())
    assert cb.base_package == "com.acme"
    assert {k: m.display for k, m in cb.modules.items()} == {"orders": "Orders", "customers": "Customers", "notify": "Notifications"}
    deps = java_code.module_dependencies(cb)
    assert deps[("orders", "customers")]["allowed"] and not deps[("orders", "customers")]["internal"]
    assert deps[("notify", "orders")]["internal"] == ["com.acme.orders.internal.OrderService"]     # reaches into internals
    routes = {(r.method, r.path) for r in java_code.routes(cb)}
    assert {("POST", "/api/orders"), ("GET", "/api/orders/{id}"), ("WS", "/ws")} <= routes
    assert any(m == "SCHEDULED" and p.startswith("OrderListener.drain") for m, p in routes)
    assert ("GET", "/never") not in routes                                                        # test sources ignored
    ls = {(x.technology, x.channel) for x in java_code.listeners(cb)}
    assert ("spring-event", "OrderPlaced") in ls and ("redis-pubsub", "order:*") in ls
    svc = cb.classes["com.acme.orders.internal.OrderService"]
    fx = java_code.method_effects(cb, svc, next(m for m in svc.methods if m.name == "place"))
    assert fx.writes == {"orders"} and "customers" in fx.reads and fx.events == {"OrderPlaced"} and fx.modules == {"customers"}
    hints = cb.classes["com.acme.notify.Hints"]
    assert java_code.method_effects(cb, hints, next(m for m in hints.methods if m.name == "signal")).pubsub == {"order:*"}
    assert java_code.cycles({("a", "b"), ("b", "a"), ("b", "c")}) == {("a", "b"), ("b", "a")}


def test_repository_and_flows(tmp_path: Path):
    r = analyze_repository(_repo(tmp_path), "rev", "shop")
    e = {(o.attributes["source"], o.kind, o.attributes["target"]): o.attributes for o in r.observations if o.subject_kind == "edge"}
    app = "container:shop/app"
    assert (app, "calls", "container:shop/cache") in e                                      # CACHE_HOST=cache (bare host)
    assert e[("component:shop/app/notify", "depends-on", "component:shop/app/orders")].get("boundary_violation")
    assert (app, "publishes", "channel:shop/order:*") in e and (app, "consumes", "channel:shop/order:*") in e
    assert ("container:shop/cache", "contains", "channel:shop/order:*") in e
    obs = [{"id": uuid.uuid4(), "connector_id": uuid.UUID(int=1), "scan_id": uuid.UUID(int=2), "observed_at": datetime.now(UTC),
            **o.model_dump()} for o in r.observations]
    by = {f["name"]: f for f in flows.recognize(builder.build(obs, {}))["flows"]}

    def hops(name):
        names = {p["key"]: p["name"] for p in by[name]["participants"]}
        return [(names[s["from"]], s["kind"], names[s["to"]]) for s in by[name]["steps"]]
    place = hops("POST /api/orders")
    assert ("Orders", "writes", "orders") in place and ("Orders", "publishes", "OrderPlaced") in place
    assert ("OrderPlaced", "delivers", "Notifications") in place and ("Notifications", "publishes", "order:*") in place
    assert ("order:*", "delivers", "app") in place
    assert "Event: OrderPlaced" in by
