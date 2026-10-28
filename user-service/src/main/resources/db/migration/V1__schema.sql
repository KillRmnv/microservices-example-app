-- User schema: roles/permissions, role mapping and users in one shot.

CREATE TABLE permissions
(
    id   BIGSERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE roles
(
    id   BIGSERIAL PRIMARY KEY,
    name VARCHAR(30) NOT NULL UNIQUE
);

CREATE TABLE role_permissions
(
    role_id       BIGINT NOT NULL REFERENCES roles (id) ON DELETE CASCADE,
    permission_id BIGINT NOT NULL REFERENCES permissions (id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

-- Permissions (7 items)
INSERT INTO permissions (name)
VALUES ('CREATE_BOOKING'),
       ('READ_BOOKING'),
       ('CANCEL_BOOKING'),
       ('EVENT_CREATE'),
       ('EVENT_UPDATE'),
       ('USER_MANAGE'),
       ('ADMIN_BYPASS');

-- Roles (3 items)
INSERT INTO roles (name)
VALUES ('CUSTOMER'),
       ('EVENT_MANAGER'),
       ('ADMIN');

-- Role → Permission mapping

-- CUSTOMER: CREATE_BOOKING, CANCEL_BOOKING, READ_BOOKING
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.name = 'CUSTOMER'
  AND p.name IN ('CREATE_BOOKING', 'CANCEL_BOOKING', 'READ_BOOKING');

-- EVENT_MANAGER: EVENT_CREATE, EVENT_UPDATE, READ_BOOKING
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.name = 'EVENT_MANAGER'
  AND p.name IN ('EVENT_CREATE', 'EVENT_UPDATE', 'READ_BOOKING');

-- ADMIN: all 7 permissions
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.name = 'ADMIN';

-- ---------------------------------------------------------------- users

CREATE TABLE IF NOT EXISTS users (
                                     id BIGSERIAL PRIMARY KEY,
                                     username VARCHAR(256) NOT NULL UNIQUE,
                                     email VARCHAR(256) NOT NULL UNIQUE,
                                     password_hash VARCHAR(256) NOT NULL,
                                     role_id BIGINT NOT NULL DEFAULT 1,
                                     is_system BOOLEAN NOT NULL DEFAULT FALSE,
                                     CONSTRAINT fk_users_role
                                         FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE RESTRICT
);

CREATE OR REPLACE FUNCTION protect_system_user_update()
    RETURNS trigger AS
$$
BEGIN
    IF OLD.is_system = TRUE THEN
        IF NEW.is_system IS DISTINCT FROM OLD.is_system THEN
            RAISE EXCEPTION 'System user flag cannot be changed';
        END IF;

        IF NEW.role_id IS DISTINCT FROM OLD.role_id THEN
            RAISE EXCEPTION 'System user role cannot be changed';
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_protect_system_user_update
    BEFORE UPDATE ON users
    FOR EACH ROW
EXECUTE FUNCTION protect_system_user_update();



CREATE OR REPLACE FUNCTION prevent_system_user_delete()
    RETURNS trigger AS
$$
BEGIN
    IF OLD.is_system = TRUE THEN
        RAISE EXCEPTION 'System user cannot be deleted';
    END IF;

    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_prevent_system_user_delete
    BEFORE DELETE ON users
    FOR EACH ROW
EXECUTE FUNCTION prevent_system_user_delete();