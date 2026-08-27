package com.microservices_example_app.gateway;

import org.junit.jupiter.api.Test;
import org.openqa.selenium.WebElement;

import static org.assertj.core.api.Assertions.assertThat;

class EventDetailViewTest extends SeleniumTestBase {

    @Test
    void shouldHaveEventRoute() {
        assertThat(jsString("return typeof App.routes['/event/:id']")).isEqualTo("function");
    }

    @Test
    void shouldExtractEventIdFromRoute() {
        assertThat(jsString("return App.matchRoute('/event/42').params.id")).isEqualTo("42");
    }

    @Test
    void shouldExtractLargeEventId() {
        assertThat(jsString("return App.matchRoute('/event/999999').params.id")).isEqualTo("999999");
    }

    @Test
    void shouldHaveMyTicketsRoute() {
        assertThat(jsString("return typeof App.routes['/my-tickets']")).isEqualTo("function");
    }

    @Test
    void shouldHaveLoginRoute() {
        assertThat(jsString("return typeof App.routes['/login']")).isEqualTo("function");
    }

    @Test
    void shouldHaveRegisterRoute() {
        assertThat(jsString("return typeof App.routes['/register']")).isEqualTo("function");
    }

    @Test
    void shouldHaveForgotPasswordRoute() {
        assertThat(jsString("return typeof App.routes['/forgot-password']")).isEqualTo("function");
    }

    @Test
    void shouldHaveResetPasswordRoute() {
        assertThat(jsString("return typeof App.routes['/reset-password']")).isEqualTo("function");
    }

    @Test
    void shouldHaveContentArea() {
        assertThat(find("#content")).isNotNull();
    }

    @Test
    void shouldHaveModalForTickets() {
        assertThat(find("#modal-overlay")).isNotNull();
    }

    @Test
    void shouldOpenModalWithTicketInfo() {
        js("App.showModal('<div>Buy Ticket</div>')");
        WebElement modalContent = find("#modal-content");
        assertThat(modalContent.getText()).contains("Buy Ticket");
    }

    @Test
    void shouldCloseModalOnOverlayClick() {
        js("App.showModal('<p>test</p>')");
        js("document.getElementById('modal-overlay').click()");
        waitForJs();
    }
}
