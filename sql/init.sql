-- 1. PERMISOS
INSERT INTO permissions (id, code, name, description, created_at)
VALUES 
  (gen_random_uuid(), 'apps:create', 'Crear Apps', 'Permite crear nuevas aplicaciones', NOW()),
  (gen_random_uuid(), 'apps:read', 'Leer Apps', 'Permite ver las aplicaciones', NOW()),
  (gen_random_uuid(), 'apps:update', 'Actualizar Apps', 'Permite modificar aplicaciones existentes', NOW()),
  (gen_random_uuid(), 'apps:delete', 'Eliminar Apps', 'Permite eliminar aplicaciones', NOW()),
  (gen_random_uuid(), 'functions:create', 'Crear Funciones', 'Permite crear funciones', NOW()),
  (gen_random_uuid(), 'functions:read', 'Leer Funciones', 'Permite ver funciones', NOW()),
  (gen_random_uuid(), 'functions:update', 'Actualizar Funciones', 'Permite actualizar funciones', NOW()),
  (gen_random_uuid(), 'functions:delete', 'Eliminar Funciones', 'Permite eliminar funciones', NOW()),
  (gen_random_uuid(), 'strategies:create', 'Crear Estrategias', 'Permite crear estrategias', NOW()),
  (gen_random_uuid(), 'strategies:read', 'Leer Estrategias', 'Permite ver estrategias', NOW()),
  (gen_random_uuid(), 'strategies:update', 'Actualizar Estrategias', 'Permite actualizar estrategias', NOW()),
  (gen_random_uuid(), 'strategies:delete', 'Eliminar Estrategias', 'Permite eliminar estrategias', NOW()),
  (gen_random_uuid(), 'proxies:create', 'Crear Proxies', 'Permite crear proxies', NOW()),
  (gen_random_uuid(), 'proxies:read', 'Leer Proxies', 'Permite ver proxies', NOW()),
  (gen_random_uuid(), 'proxies:update', 'Actualizar Proxies', 'Permite actualizar proxies', NOW()),
  (gen_random_uuid(), 'proxies:delete', 'Eliminar Proxies', 'Permite eliminar proxies', NOW()),
  (gen_random_uuid(), 'mcp:create', 'Crear MCP', 'Permite crear integraciones MCP', NOW()),
  (gen_random_uuid(), 'mcp:read', 'Leer MCP', 'Permite leer integraciones MCP', NOW()),
  (gen_random_uuid(), 'mcp:update', 'Actualizar MCP', 'Permite actualizar integraciones MCP', NOW()),
  (gen_random_uuid(), 'mcp:delete', 'Eliminar MCP', 'Permite eliminar integraciones MCP', NOW());

-- 2. ROLES
INSERT INTO roles (id, name, description, created_at)
VALUES
  (gen_random_uuid(), 'admin', 'Acceso total al sistema', NOW()),
  (gen_random_uuid(), 'user', 'Acceso limitado solo a sus recursos', NOW());

-- 3. ASIGNAR PERMISOS A LOS ROLES
-- Admin → todos los permisos
INSERT INTO role_permissions (role_id, permission_id)
SELECT
  (SELECT id FROM roles WHERE name = 'admin'),
  id FROM permissions;

-- User → solo puede leer funciones
INSERT INTO role_permissions (role_id, permission_id)
SELECT
  (SELECT id FROM roles WHERE name = 'user'),
  id FROM permissions WHERE code = 'functions:read';

-- 4. EVENT DEFINITIONS
INSERT INTO event_definitions (id, code, name, description, required_config, created_at)
VALUES 
  (gen_random_uuid(), 'new_db_row', 'Nuevo registro en tabla', 'Detecta un nuevo registro en una tabla específica de una base de datos conectada',
   '{"database_connection_id": "UUID", "table_name": "str", "time_field": "str"}'::jsonb, NOW()),

  (gen_random_uuid(), 'new_user_signup', 'Nuevo registro de usuario', 'Un nuevo usuario se ha registrado en tu sistema',
   '{"email_field": "str", "timestamp_field": "str"}'::jsonb, NOW()),

  (gen_random_uuid(), 'webhook_received', 'Webhook recibido', 'Se ha recibido un webhook en un endpoint determinado',
   '{"path": "str", "method": "str"}'::jsonb, NOW()),

  (gen_random_uuid(), 'api_event_triggered', 'Llamada API externa', 'Una API externa ha hecho una llamada que debe generar un evento',
   '{"auth_token": "str", "endpoint": "str"}'::jsonb, NOW()),

  (gen_random_uuid(), 'cron_trigger', 'Trigger por horario (cron)', 'El evento se ejecuta basado en un patrón de tiempo definido',
   '{"cron_expression": "str"}'::jsonb, NOW());
