"""Kafka metadata connector (read-only — AT-DATA_TOPOLOGY-002). confluent-kafka AdminClient + Schema Registry REST.

Reads cluster metadata only: brokers, topics/partitions, consumer groups, committed offsets and high watermarks (lag),
and Schema Registry subjects. It never consumes payloads, never joins a consumer group (offsets come from the admin API,
watermarks from an unsubscribed consumer with auto-commit off) and never writes.

Producers/consumers are attributed to services only from evidence: a consumer group's membership is runtime evidence
for `consumer-group -consumes-> topic`; mapping a group to a service needs an explicit `group_services` entry (or a
group id equal to a known compose service, confidence 0.7). Producers are never guessed — they come from code analysis
or the OTel service graph, otherwise they stay UNKNOWN.

Keys: `kafka-topic:{system}/{service}/{topic}`, `consumer-group:{system}/{service}/{group}`, `event-schema:{system}/{service}/{subject}`
where `service` is the compose service running the broker (same cluster identity the code analyzer derives from
bootstrap URLs).
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Any

from archtwin.common.egress import EgressDenied, check_url, guarded_get
from archtwin.connectors.sdk import ScanResult, TestResult

V = "kafka-admin/1.0"
INTERNAL = ("__consumer_offsets", "__transaction_state", "_schemas", "__cluster_metadata")


def _brokers(cfg: dict[str, Any]) -> list[tuple[str, int]]:
    out = []
    for b in str(cfg.get("bootstrap_servers") or "").split(","):
        b = b.strip().removeprefix("PLAINTEXT://").removeprefix("SASL_SSL://").removeprefix("SSL://")
        if b:
            host, sep, port = b.rpartition(":")
            if not sep or not port.isdigit():          # "kafka" / "[::1]" without a port => default listener
                host, port = b, "9092"
            out.append((host, int(port)))
    if not out:
        raise ValueError("bootstrap_servers is required")
    return out


def _check(cfg: dict[str, Any]) -> None:
    for h, p in _brokers(cfg):
        check_url(f"http://{h}:{p}/")
    if cfg.get("schema_registry_url"):
        check_url(str(cfg["schema_registry_url"]))


def _client_conf(cfg: dict[str, Any], secret: dict[str, Any]) -> dict[str, Any]:
    conf: dict[str, Any] = {"bootstrap.servers": ",".join(f"{h}:{p}" for h, p in _brokers(cfg)), "client.id": "archtwin-metadata",
                            "socket.timeout.ms": 10000}
    proto = cfg.get("security_protocol")
    if proto:
        conf["security.protocol"] = proto
    if secret.get("sasl_username"):
        conf.update({"sasl.mechanism": cfg.get("sasl_mechanism") or "PLAIN", "sasl.username": secret["sasl_username"],
                     "sasl.password": secret.get("sasl_password", "")})
    return conf


class KafkaClusterConnector:
    kind = "kafka"
    flag = "connector.kafka"
    manifest = {"name": "Kafka cluster (metadata)", "category": "messaging", "origin": "runtime",
                "scopes": ["Describe on cluster/topics/groups", "Read on groups' committed offsets (no payloads)"],
                "freshness_sla_s": 3600,
                "config": {"bootstrap_servers": "kafka:9092", "system": "system the cluster belongs to",
                           "service": "compose service running the broker (default: first bootstrap host)",
                           "schema_registry_url": "optional, e.g. http://schema-registry:8081",
                           "group_services": {"<consumer group>": "<compose service>"}, "include_internal": False,
                           "security_protocol": "PLAINTEXT | SSL | SASL_SSL", "sasl_mechanism": "PLAIN | SCRAM-SHA-512"},
                "secret": {"sasl_username": "", "sasl_password": ""}}

    # ------------------------------------------------------------------ sync helpers (librdkafka is blocking)
    def _admin(self, cfg, secret):
        from confluent_kafka.admin import AdminClient
        return AdminClient(_client_conf(cfg, secret))

    def _test_sync(self, cfg, secret) -> TestResult:
        a = self._admin(cfg, secret)
        md = a.list_topics(timeout=10)
        warnings = []
        try:   # excess-privilege probe: describing ACLs works only for cluster admins
            from confluent_kafka.admin import AclBindingFilter, AclOperation, AclPermissionType, ResourcePatternType, ResourceType
            f = AclBindingFilter(ResourceType.ANY, None, ResourcePatternType.ANY, None, None, AclOperation.ANY, AclPermissionType.ANY)
            a.describe_acls(f, request_timeout=5).result()
            warnings.append("credentials can describe ACLs (cluster-admin level); a Describe-only principal is enough")
        except Exception:  # noqa: BLE001 — expected for least-privilege principals or clusters without an authorizer
            pass
        return TestResult(ok=True, scopes=self.manifest["scopes"], warnings=warnings,
                          details={"cluster_id": md.cluster_id, "brokers": len(md.brokers),
                                   "topics": len([t for t in md.topics if not t.startswith("__")])})

    def _scan_sync(self, cfg, secret) -> tuple[ScanResult, list[str]]:
        from confluent_kafka import Consumer, ConsumerGroupTopicPartitions, TopicPartition
        brokers = _brokers(cfg)
        system = cfg.get("system") or "external"
        service = cfg.get("service") or brokers[0][0]
        base = f"{system}/{service}"
        r = ScanResult()
        a = self._admin(cfg, secret)
        md = a.list_topics(timeout=15)
        r.revision = f"cluster:{md.cluster_id}"
        ck = f"container:{base}"
        topics = {n: t for n, t in md.topics.items() if cfg.get("include_internal") or not n.startswith(INTERNAL)}
        for name, t in sorted(topics.items()):
            tk = f"kafka-topic:{base}/{name}"
            parts = len(t.partitions)
            rf = len(next(iter(t.partitions.values())).replicas) if t.partitions else 0
            r.node("runtime", tk, "kafka-topic", name, V, ref=f"kafka://{service}/{name}",
                   attrs={"partitions": parts, "replication_factor": rf, "cluster_id": md.cluster_id, "technology": "Kafka topic"})
            r.edge("runtime", ck, "contains", tk, V)

        # consumer groups → committed offsets → lag against high watermarks
        groups = []
        try:
            res = a.list_consumer_groups(request_timeout=10).result()
            groups = sorted(g.group_id for g in res.valid)
        except Exception as e:  # noqa: BLE001
            r.complete = False
            r.warnings.append(f"cannot list consumer groups ({type(e).__name__}); group evidence UNKNOWN")
        described = {}
        if groups:
            for gid, fut in a.describe_consumer_groups(groups, request_timeout=10).items():
                try:
                    described[gid] = fut.result()
                except Exception:  # noqa: BLE001
                    r.warnings.append(f"cannot describe group {gid}")
        wm = Consumer({**_client_conf(cfg, secret), "group.id": f"archtwin-wm-{uuid.uuid4().hex[:8]}", "enable.auto.commit": False})
        group_services = dict(cfg.get("group_services") or {})
        known_services = set(cfg.get("known_services") or [])
        try:
            for gid in groups:
                gk = f"consumer-group:{base}/{gid}"
                d = described.get(gid)
                members = [{"client_id": m.client_id, "host": m.host} for m in (d.members if d else [])]
                lag_by_topic: dict[str, int] = {}
                try:
                    offs = a.list_consumer_group_offsets([ConsumerGroupTopicPartitions(gid)], request_timeout=10)[gid].result()
                    for tp in offs.topic_partitions or []:
                        if tp.topic not in topics or tp.offset < 0:
                            continue
                        _, high = wm.get_watermark_offsets(TopicPartition(tp.topic, tp.partition), timeout=5, cached=False)
                        lag_by_topic[tp.topic] = lag_by_topic.get(tp.topic, 0) + max(0, high - tp.offset)
                except Exception as e:  # noqa: BLE001
                    r.warnings.append(f"offsets for {gid} unavailable ({type(e).__name__})")
                state = str(getattr(d, "state", "")).split(".")[-1].lower() if d else "unknown"
                r.node("runtime", gk, "consumer-group", gid, V, ref=f"kafka://{service}/groups/{gid}",
                       attrs={"state": state, "members": members[:50], "member_count": len(members), "lag": lag_by_topic,
                              "total_lag": sum(lag_by_topic.values())})
                for topic, lag in sorted(lag_by_topic.items()):
                    r.edge("runtime", gk, "consumes", f"kafka-topic:{base}/{topic}", V, attrs={"lag": lag, "protocols": ["kafka"]})
                svc = group_services.get(gid) or (gid if gid in known_services else None)
                if svc:
                    conf = 1.0 if gid in group_services else 0.7
                    for topic, lag in sorted(lag_by_topic.items()):
                        r.edge("runtime", f"container:{system}/{svc}", "consumes", f"kafka-topic:{base}/{topic}", V, confidence=conf,
                               attrs={"via_group": gid, "lag": lag, "protocols": ["kafka"],
                                      "mapping": "configured" if gid in group_services else "group id = service name"})
        finally:
            wm.close()
        r.stats = {"topics": len(topics), "consumer_groups": len(groups), "brokers": len(md.brokers)}
        r.coverage = {"origin": "runtime", "prefixes": [f"kafka-topic:{base}/", f"consumer-group:{base}/"]}
        return r, list(topics)

    async def _schemas(self, cfg: dict[str, Any], r: ScanResult, topics: list[str]) -> None:
        url = str(cfg.get("schema_registry_url") or "").rstrip("/")
        if not url:
            return
        system = cfg.get("system") or "external"
        base = f"{system}/{cfg.get('service') or _brokers(cfg)[0][0]}"
        try:
            subjects = (await guarded_get(f"{url}/subjects", timeout=10)).json()
        except Exception as e:  # noqa: BLE001
            r.warnings.append(f"schema registry unavailable ({type(e).__name__}); schema evidence UNKNOWN")
            r.complete = False
            return
        for s in sorted(subjects)[:2000]:
            try:
                latest = (await guarded_get(f"{url}/subjects/{s}/versions/latest", timeout=10)).json()
            except Exception:  # noqa: BLE001
                continue
            sk = f"event-schema:{base}/{s}"
            r.node("runtime", sk, "event-schema", s, V, ref=f"{url}/subjects/{s}",
                   attrs={"version": latest.get("version"), "schema_id": latest.get("id"), "schema_type": latest.get("schemaType", "AVRO"),
                          "schema": str(latest.get("schema", ""))[:4000]})
            topic = s.removesuffix("-value").removesuffix("-key")       # TopicNameStrategy
            if topic in topics:
                r.edge("runtime", f"kafka-topic:{base}/{topic}", "implements", sk, V, attrs={"strategy": "TopicNameStrategy"})
        r.coverage["prefixes"].append(f"event-schema:{base}/")
        r.stats["schemas"] = len([o for o in r.observations if o.kind == "event-schema"])

    async def test(self, cfg: dict[str, Any], secret: dict[str, Any]) -> TestResult:
        try:
            _check(cfg)
            res = await asyncio.to_thread(self._test_sync, cfg, secret)
            if cfg.get("schema_registry_url"):
                try:
                    subj = (await guarded_get(f"{str(cfg['schema_registry_url']).rstrip('/')}/subjects", timeout=10)).json()
                    res.details["schema_subjects"] = len(subj)
                except Exception as e:  # noqa: BLE001
                    res.warnings.append(f"schema registry unreachable: {type(e).__name__}")
            return res
        except (EgressDenied, ValueError) as e:
            return TestResult(ok=False, warnings=[str(e)])
        except Exception as e:  # noqa: BLE001
            return TestResult(ok=False, warnings=[f"{type(e).__name__}: {str(e)[:200]}"])

    async def scan(self, cfg: dict[str, Any], secret: dict[str, Any], ref: str | None) -> ScanResult:
        _check(cfg)
        r, topics = await asyncio.to_thread(self._scan_sync, cfg, secret)
        await self._schemas(cfg, r, topics)
        return r
