package com.microservices_example_app.booking;

import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;

@Tag("integration")
@Import(TestcontainersConfiguration.class)
@SpringBootTest
class WebApplicationTests {

	@Test
	void contextLoads() {
	}

}
