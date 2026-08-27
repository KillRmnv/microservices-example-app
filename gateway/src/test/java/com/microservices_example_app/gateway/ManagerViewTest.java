package com.microservices_example_app.gateway;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class ManagerViewTest extends SeleniumTestBase {

    @Test
    void shouldHaveNoAccessViewFunction() {
        assertThat(jsString("return typeof App.noAccessView")).isEqualTo("function");
    }

    @Test
    void shouldReturnNoAccessHtml() {
        String result = jsString("return App.noAccessView()");
        assertThat(result).contains("Доступ запрещен");
        assertThat(result).contains("недостаточно прав");
    }

    @Test
    void shouldHaveManagerEventsRoute() {
        assertThat(jsString("return typeof App.routes['/manager/events']")).isEqualTo("function");
    }

    @Test
    void shouldHaveManagerEventNewRoute() {
        assertThat(jsString("return typeof App.routes['/manager/event/new']")).isEqualTo("function");
    }

    @Test
    void shouldHaveManagerVenuesRoute() {
        assertThat(jsString("return typeof App.routes['/manager/venues']")).isEqualTo("function");
    }

    @Test
    void shouldHaveManagerVenueNewRoute() {
        assertThat(jsString("return typeof App.routes['/manager/venue/new']")).isEqualTo("function");
    }

    @Test
    void shouldHaveManagerEventEditRoute() {
        assertThat(jsString("return typeof App.routes['/manager/event/:id/edit']")).isEqualTo("function");
    }

    @Test
    void shouldHaveManagerVenueEditRoute() {
        assertThat(jsString("return typeof App.routes['/manager/venue/:id/edit']")).isEqualTo("function");
    }

    @Test
    void shouldHaveAdminUsersRoute() {
        assertThat(jsString("return typeof App.routes['/admin/users']")).isEqualTo("function");
    }

    @Test
    void shouldHaveAdminTownsRoute() {
        assertThat(jsString("return typeof App.routes['/admin/towns']")).isEqualTo("function");
    }

    @Test
    void shouldHaveEventEditRouteWithParam() {
        assertThat(jsString("return App.matchRoute('/manager/event/1/edit').params.id")).isEqualTo("1");
    }

    @Test
    void shouldHaveVenueEditRouteWithParam() {
        assertThat(jsString("return App.matchRoute('/manager/venue/2/edit').params.id")).isEqualTo("2");
    }
}
