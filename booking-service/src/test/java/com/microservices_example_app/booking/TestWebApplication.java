package com.microservices_example_app.booking;

import org.springframework.boot.SpringApplication;

public class TestWebApplication {

	public static void main(String[] args) {
		SpringApplication.from(BookingServiceApplication::main).with(TestcontainersConfiguration.class).run(args);
	}

}
