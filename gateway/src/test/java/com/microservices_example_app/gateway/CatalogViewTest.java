package com.microservices_example_app.gateway;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class CatalogViewTest extends SeleniumTestBase {

    @Test
    void shouldRenderEventsPageChrome() {
        navigateTo("/events");
        assertThat(findByTestId("events-page-wrap")).isNotNull();
        assertMastheadPresent();
    }

    @Test
    void shouldShowErrorStateOnEventsPageWithoutBackend() {
        navigateTo("/events");
        assertThat(findByTestId("page-error").getText()).contains("Выпуск не поступил");
        assertThat(findByTestId("retry-button").getText()).isEqualTo("Повторить");
    }

    @Test
    void shouldHaveReturnLinkOnEventsPage() {
        navigateTo("/events");
        assertThat(findByTestId("masthead-return-link").getAttribute("href")).endsWith("/");
    }

    @Test
    void shouldShowErrorStateOnPlacesPageWithoutBackend() {
        navigateTo("/places");
        assertThat(findByTestId("page-error").getText()).contains("Выпуск не поступил");
        assertThat(findByTestId("retry-button")).isNotNull();
    }

    @Test
    void shouldShowErrorStateOnEventDetailWithoutBackend() {
        navigateTo("/events/detail?id=1");
        assertThat(findByTestId("page-error")).isNotNull();
    }

    @Test
    void shouldShowErrorStateOnVenueDetailWithoutBackend() {
        navigateTo("/places/detail?id=1");
        assertThat(findByTestId("page-error")).isNotNull();
    }
}
