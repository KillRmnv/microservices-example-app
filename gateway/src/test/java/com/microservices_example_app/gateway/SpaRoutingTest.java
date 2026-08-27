package com.microservices_example_app.gateway;

import org.junit.jupiter.api.Test;
import org.openqa.selenium.WebElement;

import static org.assertj.core.api.Assertions.assertThat;

class SpaRoutingTest extends SeleniumTestBase {

    @Test
    void shouldHaveAppObjectDefined() {
        assertThat(jsString("return typeof App !== 'undefined' ? 'defined' : 'undefined'")).isEqualTo("defined");
    }

    @Test
    void shouldHaveAuthObjectDefined() {
        assertThat(jsString("return typeof Auth !== 'undefined' ? 'defined' : 'undefined'")).isEqualTo("defined");
    }

    @Test
    void shouldHaveApiObjectDefined() {
        assertThat(jsString("return typeof API !== 'undefined' ? 'defined' : 'undefined'")).isEqualTo("defined");
    }

    @Test
    void shouldHaveRoutesObject() {
        assertThat(jsString("return typeof App.routes === 'object' ? 'object' : 'other'")).isEqualTo("object");
    }

    @Test
    void shouldHaveHandleRouteFunction() {
        assertThat(jsString("return typeof App.handleRoute")).isEqualTo("function");
    }

    @Test
    void shouldHaveMatchRouteFunction() {
        assertThat(jsString("return typeof App.matchRoute")).isEqualTo("function");
    }

    @Test
    void shouldHaveNavigateFunction() {
        assertThat(jsString("return typeof App.navigate")).isEqualTo("function");
    }

    @Test
    void shouldHaveShowModalFunction() {
        assertThat(jsString("return typeof App.showModal")).isEqualTo("function");
    }

    @Test
    void shouldHaveCloseModalFunction() {
        assertThat(jsString("return typeof App.closeModal")).isEqualTo("function");
    }

    @Test
    void shouldHaveShowAlertFunction() {
        assertThat(jsString("return typeof App.showAlert")).isEqualTo("function");
    }

    @Test
    void shouldHaveFormatDateFunction() {
        assertThat(jsString("return typeof App.formatDate")).isEqualTo("function");
    }

    @Test
    void shouldHaveEscapeHtmlFunction() {
        assertThat(jsString("return typeof App.escapeHtml")).isEqualTo("function");
    }

    @Test
    void shouldHaveNoAccessViewFunction() {
        assertThat(jsString("return typeof App.noAccessView")).isEqualTo("function");
    }

    @Test
    void shouldMatchRootRoute() {
        assertThat(jsString("return App.matchRoute('/').route")).isEqualTo("/");
    }

    @Test
    void shouldMatchEmptyRoute() {
        assertThat(jsString("return App.matchRoute('').route")).isEqualTo("");
    }

    @Test
    void shouldMatchLoginRoute() {
        assertThat(jsString("return App.matchRoute('/login').route")).isEqualTo("/login");
    }

    @Test
    void shouldMatchRegisterRoute() {
        assertThat(jsString("return App.matchRoute('/register').route")).isEqualTo("/register");
    }

    @Test
    void shouldMatchForgotPasswordRoute() {
        assertThat(jsString("return App.matchRoute('/forgot-password').route")).isEqualTo("/forgot-password");
    }

    @Test
    void shouldMatchResetPasswordRoute() {
        assertThat(jsString("return App.matchRoute('/reset-password').route")).isEqualTo("/reset-password");
    }

    @Test
    void shouldMatchMyTicketsRoute() {
        assertThat(jsString("return App.matchRoute('/my-tickets').route")).isEqualTo("/my-tickets");
    }

    @Test
    void shouldMatchAdminUsersRoute() {
        assertThat(jsString("return App.matchRoute('/admin/users').route")).isEqualTo("/admin/users");
    }

    @Test
    void shouldMatchAdminTownsRoute() {
        assertThat(jsString("return App.matchRoute('/admin/towns').route")).isEqualTo("/admin/towns");
    }

    @Test
    void shouldMatchManagerEventsRoute() {
        assertThat(jsString("return App.matchRoute('/manager/events').route")).isEqualTo("/manager/events");
    }

    @Test
    void shouldMatchManagerVenuesRoute() {
        assertThat(jsString("return App.matchRoute('/manager/venues').route")).isEqualTo("/manager/venues");
    }

    @Test
    void shouldMatchEventByIdRoute() {
        assertThat(jsString("return App.matchRoute('/event/123').params.id")).isEqualTo("123");
    }

    @Test
    void shouldMatchManagerEventEditRoute() {
        assertThat(jsString("return App.matchRoute('/manager/event/456/edit').params.id")).isEqualTo("456");
    }

    @Test
    void shouldMatchManagerVenueEditRoute() {
        assertThat(jsString("return App.matchRoute('/manager/venue/789/edit').params.id")).isEqualTo("789");
    }

    @Test
    void shouldReturnNullForUnknownRoute() {
        Object result = js("return App.matchRoute('/unknown-route')");
        assertThat(result).isNull();
    }

    @Test
    void shouldEscapeHtmlEntities() {
        String result = jsString("return App.escapeHtml('<script>alert(1)</script>')");
        assertThat(result).contains("&lt;script&gt;");
        assertThat(result).doesNotContain("<script>");
    }

    @Test
    void shouldEscapeAmpersand() {
        assertThat(jsString("return App.escapeHtml('a & b')")).isEqualTo("a &amp; b");
    }

    @Test
    void shouldEscapeQuotes() {
        assertThat(jsString("return App.escapeHtml('\"hello\"')")).isEqualTo("&quot;hello&quot;");
    }

    @Test
    void shouldFormatDate() {
        assertThat(jsString("return App.formatDate('2026-05-01T19:00:00')")).isNotEmpty();
    }

    @Test
    void shouldFormatNullDate() {
        assertThat(jsString("return App.formatDate(null)")).isEqualTo("-");
    }

    @Test
    void shouldFormatEmptyDate() {
        assertThat(jsString("return App.formatDate('')")).isEqualTo("-");
    }

    @Test
    void shouldReturnNoAccessHtml() {
        String result = jsString("return App.noAccessView()");
        assertThat(result).contains("Доступ запрещен");
        assertThat(result).contains("недостаточно прав");
    }

    @Test
    void shouldOpenModal() {
        js("App.showModal('<p>test</p>')");
        WebElement overlay = find("#modal-overlay");
        assertThat(overlay.getAttribute("class")).doesNotContain("hidden");
        assertThat(find("#modal-content").getText()).contains("test");
    }

    @Test
    void shouldCloseModal() {
        js("App.showModal('<p>test</p>')");
        js("App.closeModal()");
        WebElement overlay = find("#modal-overlay");
        assertThat(overlay.getAttribute("class")).contains("hidden");
    }

    @Test
    void shouldNotHaveLoggedInClassByDefault() {
        assertThat(jsString("return document.body.classList.contains('logged-in')")).isEqualTo("false");
    }

    @Test
    void shouldNotHaveAdminClassByDefault() {
        assertThat(jsString("return document.body.classList.contains('role-admin')")).isEqualTo("false");
    }

    @Test
    void shouldNotHaveManagerClassByDefault() {
        assertThat(jsString("return document.body.classList.contains('role-event_manager')")).isEqualTo("false");
    }
}
