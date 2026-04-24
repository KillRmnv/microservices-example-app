

CREATE TABLE IF NOT EXISTS users (
    id serial primary key,
    username varchar(256) not null unique ,
    email varchar(256) not null unique ,
    password_hash varchar(256) not null,
    role_id int default 1,
    foreign key (role_id) references roles(id) on delete set default

);