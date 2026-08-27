package com.microservices_example_app.gateway;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class RoleVisibilityTest extends SeleniumTestBase {

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

    @Test
    void shouldAddLoggedInClass() {
        js("document.body.classList.add('logged-in')");
        assertThat(jsString("return document.body.classList.contains('logged-in')")).isEqualTo("true");
    }

    @Test
    void shouldAddRoleAdminClass() {
        js("document.body.classList.add('role-admin')");
        assertThat(jsString("return document.body.classList.contains('role-admin')")).isEqualTo("true");
    }

    @Test
    void shouldAddRoleEventManagerClass() {
        js("document.body.classList.add('role-event_manager')");
        assertThat(jsString("return document.body.classList.contains('role-event_manager')")).isEqualTo("true");
    }

    @Test
    void shouldAddRoleCustomerClass() {
        js("document.body.classList.add('role-customer')");
        assertThat(jsString("return document.body.classList.contains('role-customer')")).isEqualTo("true");
    }

    @Test
    void shouldReturnTrueForCanManageUsersWhenAdmin() {
        js("localStorage.setItem('userRole', 'ADMIN')");
        assertThat(jsString("return Auth.canManageUsers()")).isEqualTo("true");
    }

    @Test
    void shouldReturnFalseForCanManageUsersWhenCustomer() {
        js("localStorage.setItem('userRole', 'CUSTOMER')");
        assertThat(jsString("return Auth.canManageUsers()")).isEqualTo("false");
    }

    @Test
    void shouldReturnFalseForCanManageUsersWhenEventManager() {
        js("localStorage.setItem('userRole', 'EVENT_MANAGER')");
        assertThat(jsString("return Auth.canManageUsers()")).isEqualTo("false");
    }

    @Test
    void shouldReturnTrueForCanManageEventsWhenAdmin() {
        js("localStorage.setItem('userRole', 'ADMIN')");
        assertThat(jsString("return Auth.canManageEvents()")).isEqualTo("true");
    }

    @Test
    void shouldReturnTrueForCanManageEventsWhenEventManager() {
        js("localStorage.setItem('userRole', 'EVENT_MANAGER')");
        assertThat(jsString("return Auth.canManageEvents()")).isEqualTo("true");
    }

    @Test
    void shouldReturnFalseForCanManageEventsWhenCustomer() {
        js("localStorage.setItem('userRole', 'CUSTOMER')");
        assertThat(jsString("return Auth.canManageEvents()")).isEqualTo("false");
    }

    @Test
    void shouldReturnTrueForIsAdminWhenAdmin() {
        js("localStorage.setItem('userRole', 'ADMIN')");
        assertThat(jsString("return Auth.isAdmin()")).isEqualTo("true");
    }

    @Test
    void shouldReturnFalseForIsAdminWhenCustomer() {
        js("localStorage.setItem('userRole', 'CUSTOMER')");
        assertThat(jsString("return Auth.isAdmin()")).isEqualTo("false");
    }

    @Test
    void shouldReturnTrueForIsEventManagerWhenEventManager() {
        js("localStorage.setItem('userRole', 'EVENT_MANAGER')");
        assertThat(jsString("return Auth.isEventManager()")).isEqualTo("true");
    }

    @Test
    void shouldReturnFalseForIsEventManagerWhenAdmin() {
        js("localStorage.setItem('userRole', 'ADMIN')");
        assertThat(jsString("return Auth.isEventManager()")).isEqualTo("false");
    }

    @Test
    void shouldReturnTrueForIsCustomerWhenCustomer() {
        js("localStorage.setItem('userRole', 'CUSTOMER')");
        assertThat(jsString("return Auth.isCustomer()")).isEqualTo("true");
    }

    @Test
    void shouldReturnFalseForIsCustomerWhenAdmin() {
        js("localStorage.setItem('userRole', 'ADMIN')");
        assertThat(jsString("return Auth.isCustomer()")).isEqualTo("false");
    }

    @Test
    void shouldReturnFalseForIsLoggedInWhenNoToken() {
        js("localStorage.removeItem('token')");
        assertThat(jsString("return Auth.isLoggedIn()")).isEqualTo("false");
    }

    @Test
    void shouldReturnFalseForIsLoggedInWhenExpiredToken() {
        js("localStorage.setItem('token', 'eyJhbGciOiJIUzI1NiJ9.eyJleHAiOjF9.abc')");
        assertThat(jsString("return Auth.isLoggedIn()")).isEqualTo("false");
    }

    @Test
    void shouldGetUserRoleFromStorage() {
        js("localStorage.setItem('userRole', 'ADMIN')");
        assertThat(jsString("return Auth.getUserRole()")).isEqualTo("ADMIN");
    }

    @Test
    void shouldGetUserEmailFromStorage() {
        js("localStorage.setItem('userEmail', 'test@mail.com')");
        assertThat(jsString("return Auth.getUserEmail()")).isEqualTo("test@mail.com");
    }

    @Test
    void shouldClearSession() {
        js("Auth.setSession('token123', 'test@mail.com', 'ADMIN', '1')");
        js("Auth.clearSession()");
        assertThat(js("return Auth.getToken()")).isNull();
        assertThat(js("return Auth.getUserEmail()")).isNull();
        assertThat(js("return Auth.getUserRole()")).isNull();
    }

    @Test
    void shouldSetSession() {
        js("Auth.setSession('token123', 'admin@mail.com', 'ADMIN', '42')");
        assertThat(jsString("return Auth.getToken()")).isEqualTo("token123");
        assertThat(jsString("return Auth.getUserEmail()")).isEqualTo("admin@mail.com");
        assertThat(jsString("return Auth.getUserRole()")).isEqualTo("ADMIN");
        assertThat(jsString("return Auth.getUserId()")).isEqualTo("42");
    }

    @Test
    void shouldHaveRoleClassOnBodyForAdmin() {
        js("document.body.classList.add('role-admin')");
        assertThat(jsString("return document.body.className")).contains("role-admin");
    }

    @Test
    void shouldHaveRoleClassOnBodyForEventManager() {
        js("document.body.classList.add('role-event_manager')");
        assertThat(jsString("return document.body.className")).contains("role-event_manager");
    }

    @Test
    void shouldHaveRoleClassOnBodyForCustomer() {
        js("document.body.classList.add('role-customer')");
        assertThat(jsString("return document.body.className")).contains("role-customer");
    }
}
