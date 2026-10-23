package com.microservices_example_app.gateway;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class ChatViewTest extends SeleniumTestBase {

    private void openChat() {
        navigateTo("/");
        findByTestId("assistant-fab").click();
        assertThat(findByTestId("chat-panel")).isNotNull();
    }

    @Test
    void shouldOpenChatPanelFromFab() {
        openChat();
        assertThat(findByTestId("chat-input")).isNotNull();
        assertThat(findByTestId("chat-send")).isNotNull();
    }

    @Test
    void shouldShowOnlineModeWithoutMockFlag() {
        openChat();
        // CI builds the frontend without NEXT_PUBLIC_ASSISTANT_MOCK.
        assertThat(find(".chat-panel .kicker").getText()).contains("ОНЛАЙН");
    }

    @Test
    void shouldCloseChatPanel() {
        openChat();
        clickByTestId("chat-close");
        new org.openqa.selenium.support.ui.WebDriverWait(driver, java.time.Duration.ofSeconds(10))
                .until(d -> d.findElements(org.openqa.selenium.By.cssSelector("[data-testid='chat-panel']")).isEmpty());
    }

    @Test
    void shouldEchoUserMessage() {
        openChat();
        findByTestId("chat-input").sendKeys("Что-нибудь на выходные");
        findByTestId("chat-send").click();
        assertThat(findByTestId("chat-user-message").getText())
                .isEqualTo("Что-нибудь на выходные");
    }

    @Test
    void shouldShowErrorWithoutBackend() {
        openChat();
        findByTestId("chat-input").sendKeys("Тихий джаз в субботу");
        findByTestId("chat-send").click();
        // No backend behind the static export: the panel must say so.
        assertThat(findByTestId("chat-error").getText()).contains("ассистент");
    }
}
