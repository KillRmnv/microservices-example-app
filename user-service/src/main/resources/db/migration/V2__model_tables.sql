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