package com.microservices_example_app.gateway;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import static org.assertj.core.api.Assertions.assertThat;

class NavigationTest extends SeleniumTestBase {

    /** Pages that always render the newspaper masthead, even without a backend. */
    @ParameterizedTest
    @ValueSource(strings = {"/", "/events", "/about"})
    void shouldServeRouteWithMasthead(String path) {
        navigateTo(path);
        assertMastheadPresent();
    }

    /** Auth pages use their own compact brand block instead of the masthead. */
    @ParameterizedTest
    @ValueSource(strings = {"/login", "/register", "/forgot-password", "/reset-password"})
    void shouldServeAuthRouteWithBrand(String path) {
        navigateTo(path);
        assertThat(find(".auth-logo").getText()).isEqualTo("ДОСУГ");
    }

    /** Admin and manager are guarded; the profile redirects to auth. */
    @ParameterizedTest
    @ValueSource(strings = {"/admin", "/manager"})
    void shouldServeGuardedRouteWithNoAccess(String path) {
        navigateTo(path);
        assertThat(findByTestId("no-access")).isNotNull();
    }

    @Test
    void shouldRedirectProfileToLoginWhenLoggedOut() {
        navigateTo("/profile");
        waitForUrlContains("/login");
        assertThat(driver.getCurrentUrl()).contains("next=/profile");
        assertThat(findByTestId("login-email")).isNotNull();
    }

    @Test
    void shouldHaveCorrectDocumentTitle() {
        navigateTo("/");
        assertThat(driver.getTitle()).contains("ДОСУГ");
    }

    @Test
    void shouldHaveHtmlLangRu() {
        navigateTo("/");
        assertThat(find("html").getAttribute("lang")).isEqualTo("ru");
    }

    @Test
    void shouldHaveDocType() {
        navigateTo("/");
        assertThat(jsString("return document.doctype ? document.doctype.name : null")).isEqualTo("html");
    }

    @Test
    void shouldNavigateFromHomeToEventsViaNav() {
        navigateTo("/");
        findByTestId("nav-events").click();
        waitForUrlContains("/events");
        assertThat(findByTestId("events-page-wrap")).isNotNull();
    }

    @Test
    void shouldNavigateFromHomeToLoginViaMasthead() {
        navigateTo("/");
        findByTestId("masthead-login").click();
        waitForUrlContains("/login");
        assertThat(findByTestId("login-submit")).isNotNull();
    }
}
