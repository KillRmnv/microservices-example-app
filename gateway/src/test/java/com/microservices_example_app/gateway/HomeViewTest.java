package com.microservices_example_app.gateway;

import org.junit.jupiter.api.Test;
import org.openqa.selenium.WebElement;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class HomeViewTest extends SeleniumTestBase {

    @Test
    void shouldRenderSearchBar() {
        navigateTo("/");
        assertThat(find(".search-bar")).isNotNull();
    }

    @Test
    void shouldHaveSearchTitleInput() {
        navigateTo("/");
        WebElement input = find("#search-title");
        assertThat(input.getAttribute("placeholder")).contains("Поиск");
    }

    @Test
    void shouldHaveAdmissionModeSelect() {
        navigateTo("/");
        assertThat(find("#search-admission")).isNotNull();
    }

    @Test
    void shouldHaveVenueSelect() {
        navigateTo("/");
        assertThat(find("#search-venue")).isNotNull();
    }

    @Test
    void shouldHaveSearchButton() {
        navigateTo("/");
        assertThat(find("#search-btn").getText()).isEqualTo("Найти");
    }

    @Test
    void shouldHaveResetButton() {
        navigateTo("/");
        assertThat(find("#reset-btn").getText()).isEqualTo("Сбросить");
    }

    @Test
    void shouldHaveDateInputs() {
        navigateTo("/");
        assertThat(find("#search-starts-from").getAttribute("type")).isEqualTo("date");
        assertThat(find("#search-starts-to").getAttribute("type")).isEqualTo("date");
    }

    @Test
    void shouldHaveEventsGrid() {
        navigateTo("/");
        assertThat(find("#events-grid")).isNotNull();
    }

    @Test
    void shouldHavePaginationDiv() {
        navigateTo("/");
        assertThat(find("#pagination")).isNotNull();
    }

    @Test
    void shouldHaveAdmissionOptions() {
        navigateTo("/");
        List<WebElement> options = findAll("#search-admission option");
        assertThat(options.size()).isGreaterThanOrEqualTo(3);
    }

    @Test
    void shouldHaveCardGridClass() {
        navigateTo("/");
        assertThat(find("#events-grid").getAttribute("class")).contains("card-grid");
    }

    @Test
    void shouldHaveSearchBarInputs() {
        navigateTo("/");
        List<WebElement> inputs = findAll(".search-bar input");
        assertThat(inputs.size()).isGreaterThanOrEqualTo(3);
    }

    @Test
    void shouldHaveSearchBarSelects() {
        navigateTo("/");
        List<WebElement> selects = findAll(".search-bar select");
        assertThat(selects).hasSize(2);
    }

    @Test
    void shouldHaveSearchBarButtons() {
        navigateTo("/");
        List<WebElement> buttons = findAll(".search-bar button");
        assertThat(buttons).hasSize(2);
    }
}
