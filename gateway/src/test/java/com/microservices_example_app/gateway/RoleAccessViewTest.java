package com.microservices_example_app.gateway;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class RoleAccessViewTest extends SeleniumTestBase {

    @Test
    void shouldShowNoAccessOnProfileWhenLoggedOut() {
        navigateTo("/profile");
        assertThat(findByTestId("no-access").getText()).contains("Раздел для подписчиков");
    }

    @Test
    void shouldShowNoAccessOnAdminWhenLoggedOut() {
        navigateTo("/admin");
        assertThat(findByTestId("no-access").getText()).contains("Раздел для подписчиков");
    }

    @Test
    void shouldShowNoAccessOnManagerWhenLoggedOut() {
        navigateTo("/manager");
        assertThat(findByTestId("no-access").getText()).contains("Раздел для подписчиков");
    }

    @Test
    void shouldLinkLoginFromNoAccessView() {
        navigateTo("/profile");
        assertThat(find("a[href='/login']")).isNotNull();
    }

    @Test
    void shouldNotRenderAdminContentWhenLoggedOut() {
        navigateTo("/admin");
        assertThat(findAllByTestId("admin-page")).isEmpty();
    }

    @Test
    void shouldNotRenderManagerContentWhenLoggedOut() {
        navigateTo("/manager");
        assertThat(findAllByTestId("manager-page")).isEmpty();
    }

    @Test
    void shouldNotRenderProfileContentWhenLoggedOut() {
        navigateTo("/profile");
        assertThat(findAllByTestId("profile-page")).isEmpty();
    }
}
