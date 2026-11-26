package com.microservices_example_app.users.exceptions;

import com.microservices_example_app.users.util.SensitiveMask;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.ConstraintViolationException;
import lombok.AllArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.http.ResponseEntity;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.authorization.AuthorizationDeniedException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.net.URI;
import java.rmi.NoSuchObjectException;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;

@Slf4j
@RestControllerAdvice
@AllArgsConstructor
public class GlobalExceptionHandling {

    private static final String TYPE_BASE = "https://dosug.example/problems/";

    private static ProblemDetail problem(HttpStatus status, String code, String title,
                                         String detail, HttpServletRequest request,
                                         Map<String, Object> extra) {
        ProblemDetail pd = ProblemDetail.forStatusAndDetail(status, detail);
        pd.setType(URI.create(TYPE_BASE + code));
        pd.setTitle(title);
        pd.setInstance(URI.create(request != null ? request.getRequestURI() : "/"));
        pd.setProperty("code", code);
        pd.setProperty("traceId", resolveTraceId(request));
        if (extra != null) {
            extra.forEach(pd::setProperty);
        }
        return pd;
    }

    private static String resolveTraceId(HttpServletRequest request) {
        if (request != null) {
            String header = request.getHeader("X-Request-ID");
            if (header != null && !header.isBlank()) {
                return header;
            }
        }
        return UUID.randomUUID().toString();
    }

    @ExceptionHandler(NoSuchObjectException.class)
    public ResponseEntity<ProblemDetail> noSuchObjectException(NoSuchObjectException ex,
                                                              HttpServletRequest request) {
        log.warn("NotFoundException:{}", SensitiveMask.maskEmailsInText(ex.getMessage()));
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
                .body(problem(HttpStatus.NOT_FOUND, "not_found", HttpStatus.NOT_FOUND.getReasonPhrase(),
                        ex.getMessage(), request, null));
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<ProblemDetail> illegalArgumentException(IllegalArgumentException ex,
                                                                 HttpServletRequest request) {
        log.warn("IllegalArgumentException:{}", SensitiveMask.maskEmailsInText(ex.getMessage()));
        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                .body(problem(HttpStatus.BAD_REQUEST, "illegal_argument",
                        HttpStatus.BAD_REQUEST.getReasonPhrase(), ex.getMessage(), request, null));
    }

    @ExceptionHandler(UserAlreadyExistsException.class)
    public ResponseEntity<ProblemDetail> userAlreadyExistsException(UserAlreadyExistsException ex,
                                                                   HttpServletRequest request) {
        log.warn("UserAlreadyExistsException:{}", SensitiveMask.maskEmailsInText(ex.getMessage()));
        return ResponseEntity.status(HttpStatus.CONFLICT)
                .body(problem(HttpStatus.CONFLICT, "user_already_exists",
                        HttpStatus.CONFLICT.getReasonPhrase(), ex.getMessage(), request, null));
    }

    @ExceptionHandler(DataIntegrityViolationException.class)
    public ResponseEntity<ProblemDetail> dataIntegrityViolationException(DataIntegrityViolationException ex,
                                                                        HttpServletRequest request) {
        log.warn("DataIntegrityViolationException:{}", SensitiveMask.maskEmailsInText(ex.getMessage()));
        return ResponseEntity.status(HttpStatus.CONFLICT)
                .body(problem(HttpStatus.CONFLICT, "conflict",
                        HttpStatus.CONFLICT.getReasonPhrase(),
                        "Пользователь с таким email или именем уже существует",
                        request, null));
    }

    @ExceptionHandler(AuthorizationDeniedException.class)
    public ResponseEntity<ProblemDetail> authorizationDeniedException(AuthorizationDeniedException ex,
                                                                     HttpServletRequest request) {
        return accessDeniedException(ex, request);
    }

    @ExceptionHandler(AccessDeniedException.class)
    public ResponseEntity<ProblemDetail> accessDeniedException(AccessDeniedException ex,
                                                              HttpServletRequest request) {
        log.warn("AccessDeniedException:{}", ex.getMessage());
        return ResponseEntity.status(HttpStatus.FORBIDDEN)
                .body(problem(HttpStatus.FORBIDDEN, "forbidden",
                        HttpStatus.FORBIDDEN.getReasonPhrase(),
                        "Insufficient permissions", request, null));
    }

    @ExceptionHandler(EmailForwardingException.class)
    public ResponseEntity<ProblemDetail> emailForwardingException(EmailForwardingException ex,
                                                                 HttpServletRequest request) {
        log.warn("EmailForwardingException exception:{}", SensitiveMask.maskEmailsInText(ex.getMessage()));
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(problem(HttpStatus.INTERNAL_SERVER_ERROR, "email_forwarding_failed",
                        HttpStatus.INTERNAL_SERVER_ERROR.getReasonPhrase(), ex.getMessage(), request, null));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ProblemDetail> validationException(MethodArgumentNotValidException ex,
                                                            HttpServletRequest request) {
        List<Map<String, String>> errors = ex.getBindingResult().getFieldErrors().stream()
                .map(error -> Map.of(
                        "field", error.getField(),
                        "code", error.getCode() != null ? error.getCode() : "invalid",
                        "message", error.getDefaultMessage() != null
                                ? error.getDefaultMessage() : "Invalid value"
                ))
                .collect(Collectors.toList());
        log.warn("Validation error: {}", SensitiveMask.maskEmailsInText(errors.toString()));
        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                .body(problem(HttpStatus.BAD_REQUEST, "validation_error",
                        HttpStatus.BAD_REQUEST.getReasonPhrase(), "Validation failed",
                        request, Map.of("errors", errors)));
    }

    @ExceptionHandler(ConstraintViolationException.class)
    public ResponseEntity<ProblemDetail> constraintViolationException(ConstraintViolationException ex,
                                                                     HttpServletRequest request) {
        List<Map<String, String>> errors = ex.getConstraintViolations().stream()
                .map(v -> Map.of(
                        "field", v.getPropertyPath().toString(),
                        "code", v.getConstraintDescriptor() != null
                                && v.getConstraintDescriptor().getAnnotation() != null
                                ? v.getConstraintDescriptor().getAnnotation().annotationType().getSimpleName()
                                : "invalid",
                        "message", v.getMessage()
                ))
                .collect(Collectors.toList());
        log.warn("Constraint violation: {}", SensitiveMask.maskEmailsInText(errors.toString()));
        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                .body(problem(HttpStatus.BAD_REQUEST, "validation_error",
                        HttpStatus.BAD_REQUEST.getReasonPhrase(), "Validation failed",
                        request, Map.of("errors", errors)));
    }

    @ExceptionHandler(HttpMessageNotReadableException.class)
    public ResponseEntity<ProblemDetail> httpMessageNotReadableException(HttpMessageNotReadableException ex,
                                                                        HttpServletRequest request) {
        log.warn("HttpMessageNotReadableException:{}", SensitiveMask.maskEmailsInText(ex.getMessage()));
        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                .body(problem(HttpStatus.BAD_REQUEST, "http_message_not_readable",
                        HttpStatus.BAD_REQUEST.getReasonPhrase(), "Malformed request body",
                        request, null));
    }

    @ExceptionHandler(UserNotFoundException.class)
    public ResponseEntity<ProblemDetail> userNotFoundException(UserNotFoundException ex,
                                                              HttpServletRequest request) {
        log.warn("UserNotFoundException:{}", SensitiveMask.maskEmailsInText(ex.getMessage()));
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
                .body(problem(HttpStatus.NOT_FOUND, "user_not_found",
                        HttpStatus.NOT_FOUND.getReasonPhrase(), ex.getMessage(), request, null));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ProblemDetail> unexpectedException(Exception ex,
                                                            HttpServletRequest request) {
        log.error("Unexpected exception:{}", SensitiveMask.maskEmailsInText(ex.getMessage()), ex);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(problem(HttpStatus.INTERNAL_SERVER_ERROR, "internal_error",
                        HttpStatus.INTERNAL_SERVER_ERROR.getReasonPhrase(), "Internal server error",
                        request, null));
    }
}
