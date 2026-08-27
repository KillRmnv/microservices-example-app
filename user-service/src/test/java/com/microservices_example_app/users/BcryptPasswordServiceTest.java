package com.microservices_example_app.users;

import com.microservices_example_app.users.service.BcryptPasswordService;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.*;

class BcryptPasswordServiceTest {

    private final BcryptPasswordService passwordService = new BcryptPasswordService();


    @Test
    void hash_shouldReturnBcryptHash() {
        String hash = passwordService.hash("validPassword");

        assertThat(hash).isNotBlank();
        assertThat(hash).startsWith("$2");
        assertThat(hash).isNotEqualTo("validPassword");
    }

    @Test
    void hash_shouldThrowWhenNull() {
        assertThatThrownBy(() -> passwordService.hash(null))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("Password cannot be empty or consist of only whitespace");
    }

    @Test
    void hash_shouldThrowWhenEmpty() {
        assertThatThrownBy(() -> passwordService.hash(""))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("Password cannot be empty or consist of only whitespace");
    }

    @Test
    void hash_shouldThrowWhenBlank() {
        assertThatThrownBy(() -> passwordService.hash("   "))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("Password cannot be empty or consist of only whitespace");
    }


    @Test
    void verify_shouldReturnTrueForCorrectPassword() {
        String hash = passwordService.hash("correctPass");

        assertThat(passwordService.verify("correctPass", hash)).isTrue();
    }

    @Test
    void verify_shouldReturnFalseForWrongPassword() {
        String hash = passwordService.hash("correctPass");

        assertThat(passwordService.verify("wrongPass", hash)).isFalse();
    }

    @Test
    void verify_shouldReturnFalseWhenPasswordNull() {
        String hash = passwordService.hash("somePassword");

        assertThat(passwordService.verify(null, hash)).isFalse();
    }

    @Test
    void verify_shouldReturnFalseWhenHashNull() {
        assertThat(passwordService.verify("pass", null)).isFalse();
    }

    @Test
    void verify_shouldReturnFalseWhenHashEmpty() {
        assertThat(passwordService.verify("pass", "")).isFalse();
    }
}
