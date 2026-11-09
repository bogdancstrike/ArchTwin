CREATE TABLE warehouses (id INT AUTO_INCREMENT PRIMARY KEY, code VARCHAR(16) NOT NULL UNIQUE, city VARCHAR(64) NOT NULL);
CREATE TABLE stock (sku VARCHAR(32) NOT NULL, warehouse_id INT NOT NULL, qty INT NOT NULL DEFAULT 0, PRIMARY KEY (sku, warehouse_id),
                    CONSTRAINT fk_stock_wh FOREIGN KEY (warehouse_id) REFERENCES warehouses(id));
CREATE TABLE suppliers (id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(64) NOT NULL, contact_phone VARCHAR(32));
INSERT INTO warehouses (code, city) VALUES ('BUC1', 'Bucharest'), ('CLJ1', 'Cluj');
INSERT INTO stock (sku, warehouse_id, qty) VALUES ('sku-1', 1, 100), ('sku-2', 1, 50), ('sku-1', 2, 20);
CREATE USER 'archtwin_catalog_ro'@'%' IDENTIFIED BY 'catalog-ro';
GRANT REFERENCES ON inventory.* TO 'archtwin_catalog_ro'@'%';   -- metadata visibility only, no SELECT on rows
