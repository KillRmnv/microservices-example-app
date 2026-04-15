package com.microservices_example_app.users.service;

import com.password4j.Password;

/**
 * Интерфейс для хеширования и проверки паролей.
 *
 * <p>Абстрагирует конкретную библиотеку хеширования (password4j),
 * позволяя легко заменить реализацию в будущем.</p>
 */
public interface PasswordService {

    /**
     * Хеширует открытый пароль.
     *
     * @param plainPassword пароль в открытом виде
     * @return хеш вида $2b$12$...
     */
    String hash(String plainPassword);

    /**
     * Проверяет открытый пароль против сохранённого хеша.
     *
     * @param plainPassword пароль в открытом виде
     * @param storedHash    хеш из БД
     * @return true если пароль совпадает
     */
    boolean verify(String plainPassword, String storedHash);
}
