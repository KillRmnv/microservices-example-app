package com.microservices_example_app.gateway;

import com.microservices_example_app.gateway.filter.RouteValidator;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.mock.http.server.reactive.MockServerHttpRequest;

import static org.assertj.core.api.Assertions.assertThat;

class RouteValidatorTest {

    private final RouteValidator validator = new RouteValidator();

    @Test
    void publicCatalogReadsAreOpen() {
        assertThat(isSecure(HttpMethod.GET, "/catalog/events")).isFalse();
        assertThat(isSecure(HttpMethod.GET, "/booking/events")).isFalse();
        assertThat(isSecure(HttpMethod.GET, "/booking/venues/search")).isFalse();
        assertThat(isSecure(HttpMethod.GET, "/booking/tickets/search")).isFalse();
    }

    @Test
    void publicAssistantReadsAreOpen() {
        assertThat(isSecure(HttpMethod.POST, "/assistant/search")).isFalse();
        assertThat(isSecure(HttpMethod.POST, "/assistant/dialogue/v2")).isFalse();
        assertThat(isSecure(HttpMethod.POST, "/assistant/query")).isFalse();
        assertThat(isSecure(HttpMethod.POST, "/assistant/plan")).isFalse();
        assertThat(isSecure(HttpMethod.POST, "/assistant/holds")).isTrue();
    }

    @Test
    void mutationsStaySecured() {
        assertThat(isSecure(HttpMethod.POST, "/booking/events")).isTrue();
        assertThat(isSecure(HttpMethod.PUT, "/booking/events/1")).isTrue();
        assertThat(isSecure(HttpMethod.DELETE, "/booking/events/1")).isTrue();
        assertThat(isSecure(HttpMethod.POST, "/catalog/events")).isTrue();
    }

    @Test
    void userEndpointsStaySecured() {
        assertThat(isSecure(HttpMethod.GET, "/users/me")).isTrue();
        assertThat(isSecure(HttpMethod.POST, "/users/auth/login")).isFalse();
    }

    private boolean isSecure(HttpMethod method, String path) {
        return validator.isSecured.test(
                MockServerHttpRequest.method(method, "http://localhost" + path).build());
    }
}
