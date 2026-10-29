package com.microservices_example_app.gateway;

import org.junit.jupiter.api.Test;
import org.openqa.selenium.WebElement;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class HomeViewTest extends SeleniumTestBase {

    @Test
    void shouldRenderHomePage() {
        navigateTo("/");
        assertThat(findByTestId("home-page")).isNotNull();
    }

    @Test
    void shouldHaveMastheadBrand() {
        navigateTo("/");
        WebElement brand = find(".brand h1 a");
        assertThat(brand.getText()).isEqualTo("ДОСУГ");
        assertThat(brand.getAttribute("href")).endsWith("/");
    }

    @Test
    void shouldHaveMainNavigation() {
        navigateTo("/");
        assertThat(findByTestId("newspaper-nav")).isNotNull();
        assertThat(findByTestId("nav-home").getAttribute("href")).endsWith("/");
        assertThat(findByTestId("nav-events").getAttribute("href")).endsWith("/events");
        assertThat(findByTestId("nav-places").getAttribute("href")).endsWith("/places");
        assertThat(findByTestId("nav-profile").getAttribute("href")).endsWith("/profile");
        assertThat(findByTestId("nav-about").getAttribute("href")).endsWith("/about");
    }

    @Test
    void shouldHideManagerAndAdminNavWhenLoggedOut() {
        navigateTo("/");
        assertThat(findAllByTestId("nav-manager")).isEmpty();
        assertThat(findAllByTestId("nav-admin")).isEmpty();
    }

    @Test
    void shouldShowLoginActionWhenLoggedOut() {
        navigateTo("/");
        assertThat(findByTestId("masthead-login").getAttribute("href")).endsWith("/login");
        assertThat(findAllByTestId("masthead-logout")).isEmpty();
        assertThat(findAllByTestId("masthead-profile")).isEmpty();
    }

    @Test
    void shouldHaveFiltersSidebar() {
        navigateTo("/");
        assertThat(findByTestId("filters-sidebar")).isNotNull();
        assertThat(findByTestId("apply-filters").getText()).startsWith("Показать подборку");
        assertThat(findByTestId("reset-filters").getText()).isEqualTo("Сбросить всё");
    }

    @Test
    void shouldHaveViewSwitch() {
        navigateTo("/");
        assertThat(findByTestId("home-view-switch")).isNotNull();
        assertThat(findByTestId("view-grid").getText()).isEqualTo("Сетка");
        assertThat(findByTestId("view-map").getText()).isEqualTo("Карта");
    }

    @Test
    void shouldKeepErrorStateWhenSwitchingToMapWithoutBackend() {
        navigateTo("/");
        // The API error takes precedence over the map placeholder offline.
        findByTestId("view-map").click();
        assertThat(findByTestId("home-error")).isNotNull();
        assertThat(findAllByTestId("map-placeholder")).isEmpty();
    }

    @Test
    void shouldHaveDayTabs() {
        navigateTo("/");
        List<WebElement> tabs = findAll("[data-testid='home-day-tabs'] button");
        assertThat(tabs).hasSize(4);
        assertThat(tabs.get(0).getText()).isEqualTo("Все даты");
    }

    @Test
    void shouldHaveDateBudgetAndAtmosphereInputs() {
        navigateTo("/");
        assertThat(findByTestId("filters-date").getAttribute("type")).isEqualTo("date");
        assertThat(findByTestId("filters-budget").getAttribute("type")).isEqualTo("range");
        assertThat(find("textarea[data-testid='filters-atmosphere']")
                .getAttribute("placeholder")).contains("уютно");
    }

    @Test
    void shouldShowErrorStateWithoutBackend() {
        navigateTo("/");
        assertThat(findByTestId("home-error").getText()).contains("Не удалось связаться с редакцией");
    }

    @Test
    void shouldToggleTheme() {
        navigateTo("/");
        findByTestId("theme-toggle").click();
        assertThat(find("html").getAttribute("class")).contains("dark-mode");
    }
}
