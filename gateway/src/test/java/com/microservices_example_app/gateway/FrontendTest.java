package com.microservices_example_app.gateway;

import org.junit.jupiter.api.Test;
import org.openqa.selenium.WebElement;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class FrontendTest extends SeleniumTestBase {

    @Test
    void shouldHaveCorrectPageTitle() {
        assertThat(driver.getTitle()).isEqualTo("Event Booking System");
    }

    @Test
    void shouldHaveAppTitleInHeader() {
        WebElement title = find("#app-title");
        assertThat(title.getText()).isEqualTo("Event Booking");
    }

    @Test
    void shouldHaveMainNavigation() {
        assertThat(find("#main-nav")).isNotNull();
    }

    @Test
    void shouldHaveHomeNavLink() {
        WebElement link = find("a[data-view='home']");
        assertThat(link.getAttribute("href")).contains("#/");
        assertThat(link.getText()).isEqualTo("Каталог событий");
    }

    @Test
    void shouldHaveMyTicketsLink() {
        WebElement link = find("a[data-view='my-tickets']");
        assertThat(link.getAttribute("href")).contains("#/my-tickets");
        assertThat(link.getAttribute("textContent")).isEqualTo("Мои билеты");
    }

    @Test
    void shouldHaveAdminUsersLink() {
        WebElement link = find("a[data-view='admin-users']");
        assertThat(link.getAttribute("href")).contains("#/admin/users");
        assertThat(link.getAttribute("textContent")).isEqualTo("Пользователи");
    }

    @Test
    void shouldHaveAdminTownsLink() {
        WebElement link = find("a[data-view='admin-towns']");
        assertThat(link.getAttribute("href")).contains("#/admin/towns");
        assertThat(link.getAttribute("textContent")).isEqualTo("Города");
    }

    @Test
    void shouldHaveManagerEventsLink() {
        WebElement link = find("a[data-view='manager-events']");
        assertThat(link.getAttribute("href")).contains("#/manager/events");
        assertThat(link.getAttribute("textContent")).isEqualTo("Управление событиями");
    }

    @Test
    void shouldHaveManagerVenuesLink() {
        WebElement link = find("a[data-view='manager-venues']");
        assertThat(link.getAttribute("href")).contains("#/manager/venues");
        assertThat(link.getAttribute("textContent")).isEqualTo("Управление площадками");
    }

    @Test
    void shouldHaveAuthSection() {
        assertThat(find("#auth-section")).isNotNull();
    }

    @Test
    void shouldShowLoginButtonWhenNotLoggedIn() {
        WebElement loginBtn = find("#login-btn");
        assertThat(loginBtn.getText()).isEqualTo("Войти");
    }

    @Test
    void shouldHaveContentDiv() {
        assertThat(find("#content")).isNotNull();
    }

    @Test
    void shouldHaveLoadingSpinner() {
        assertThat(find("#loading")).isNotNull();
        assertThat(find("#loading .spinner")).isNotNull();
    }

    @Test
    void shouldHaveModalOverlay() {
        WebElement modal = find("#modal-overlay");
        assertThat(modal.getAttribute("class")).contains("hidden");
    }

    @Test
    void shouldHaveModalCloseButton() {
        assertThat(find("#modal-close")).isNotNull();
    }

    @Test
    void shouldHaveModalContent() {
        assertThat(find("#modal-content")).isNotNull();
    }

    @Test
    void shouldHaveFooter() {
        WebElement footer = find("footer");
        assertThat(footer.getText()).contains("2026");
        assertThat(footer.getText()).contains("Event Booking System");
    }

    @Test
    void shouldHaveCssLinks() {
        List<WebElement> links = findAll("link[rel='stylesheet']");
        assertThat(links).hasSize(2);
    }

    @Test
    void shouldHaveScriptTags() {
        List<WebElement> scripts = findAll("script[src]");
        assertThat(scripts).hasSize(3);
    }

    @Test
    void shouldHaveMetaViewport() {
        WebElement meta = find("meta[name='viewport']");
        assertThat(meta.getAttribute("content")).contains("width=device-width");
    }

    @Test
    void shouldHaveMetaCharset() {
        WebElement meta = find("meta[charset]");
        assertThat(meta.getAttribute("charset")).isEqualTo("UTF-8");
    }

    @Test
    void shouldHaveLoadingText() {
        WebElement loadingText = find("#loading p");
        assertThat(loadingText.getAttribute("textContent")).isEqualTo("Загрузка...");
    }

    @Test
    void shouldHaveNavLinks() {
        List<WebElement> links = findAll("#main-nav a.nav-link");
        assertThat(links).hasSize(6);
    }

    @Test
    void shouldHaveNavLinksWithCorrectDataView() {
        List<WebElement> links = findAll("#main-nav a.nav-link");
        assertThat(links).hasSize(6);
        assertThat(links.get(0).getAttribute("data-view")).isEqualTo("home");
        assertThat(links.get(1).getAttribute("data-view")).isEqualTo("my-tickets");
        assertThat(links.get(2).getAttribute("data-view")).isEqualTo("admin-users");
        assertThat(links.get(3).getAttribute("data-view")).isEqualTo("admin-towns");
        assertThat(links.get(4).getAttribute("data-view")).isEqualTo("manager-events");
        assertThat(links.get(5).getAttribute("data-view")).isEqualTo("manager-venues");
    }

    @Test
    void shouldHaveCustomerOnlyClass() {
        WebElement link = find("a[data-view='my-tickets']");
        assertThat(link.getAttribute("class")).contains("customer-only");
    }

    @Test
    void shouldHaveAdminOnlyClass() {
        WebElement link = find("a[data-view='admin-users']");
        assertThat(link.getAttribute("class")).contains("admin-only");
    }

    @Test
    void shouldHaveManagerAccessClass() {
        WebElement link = find("a[data-view='manager-events']");
        assertThat(link.getAttribute("class")).contains("manager-access");
    }

    @Test
    void shouldHaveHtmlLangEn() {
        WebElement html = find("html");
        assertThat(html.getAttribute("lang")).isEqualTo("en");
    }

    @Test
    void shouldHaveDocType() {
        String doctype = jsString("return document.doctype ? document.doctype.name : null");
        assertThat(doctype).isEqualTo("html");
    }
}
