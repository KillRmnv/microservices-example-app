package com.microservices_example_app.users.util;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Masks personally identifiable data before it reaches the logs. */
public final class SensitiveMask {

    private static final Pattern EMAIL_IN_TEXT =
            Pattern.compile("([A-Za-z0-9._%+\\-]+)@([A-Za-z0-9.\\-]+\\.[A-Za-z]{2,})");

    private SensitiveMask() {
    }

    /** Masks an email as {@code u***@domain}. Null-safe. */
    public static String maskEmail(String email) {
        if (email == null) {
            return null;
        }
        int at = email.indexOf('@');
        if (at <= 0) {
            return "***";
        }
        return email.charAt(0) + "***@" + email.substring(at + 1);
    }

    /** Masks every email-like substring inside free text. Null-safe. */
    public static String maskEmailsInText(String text) {
        if (text == null) {
            return null;
        }
        Matcher matcher = EMAIL_IN_TEXT.matcher(text);
        StringBuilder result = new StringBuilder();
        while (matcher.find()) {
            String local = matcher.group(1);
            String replacement = (local.isEmpty() ? "***" : local.charAt(0) + "***") + "@" + matcher.group(2);
            matcher.appendReplacement(result, Matcher.quoteReplacement(replacement));
        }
        matcher.appendTail(result);
        return result.toString();
    }
}
