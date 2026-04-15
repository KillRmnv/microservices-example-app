package com.microservices_example_app.booking;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;

@Import(TestcontainersConfiguration.class)
@SpringBootTest
class WebApplicationTests {

	@Test
	void contextLoads() {
	}

}
