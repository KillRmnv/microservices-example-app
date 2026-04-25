package com.microservices_example_app.users;

import org.springframework.boot.SpringApplication;

public class TestWebApplication {

	public static void main(String[] args) {
		SpringApplication.from(UserServiceApplication::main).with(TestcontainersConfiguration.class).run(args);
	}

}
