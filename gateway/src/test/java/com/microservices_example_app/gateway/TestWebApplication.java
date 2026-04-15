package com.microservices_example_app.gateway;

import org.springframework.boot.SpringApplication;

public class TestWebApplication {

	public static void main(String[] args) {
		SpringApplication.from(WebApplication::main).with(TestcontainersConfiguration.class).run(args);
	}

}
