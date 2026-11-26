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
    void shouldToggleThemeOnEventsPage() {
        navigateTo("/events");
        clickByTestId("theme-toggle");
        assertThat(find("html").getAttribute("class")).contains("dark-mode");
    }

    @Test
    void shouldKeepThemeAcrossNavigation() {
        navigateTo("/events");
        clickByTestId("theme-toggle");
        navigateTo("/");
        assertThat(find("html").getAttribute("class")).contains("dark-mode");
    }

    @Test
    void shouldOpenCityMenuOnMobile() {
        driver.manage().window().setSize(new org.openqa.selenium.Dimension(390, 844));
        navigateTo("/events");
        clickByTestId("city-picker");
        org.openqa.selenium.WebElement menu = findByTestId("nav-city-options");
        assertThat(menu.isDisplayed()).isTrue();
        driver.manage().window().setSize(new org.openqa.selenium.Dimension(1400, 1000));
    }

    @Test
    void shouldShowAssistantAndFooterOnEventsPage() {
        navigateTo("/events");
        assertThat(findByTestId("assistant-fab")).isNotNull();
        assertThat(findByTestId("site-footer")).isNotNull();
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
