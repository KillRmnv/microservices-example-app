package com.microservices_example_app.users.controller;

import com.microservices_example_app.users.dto.*;
import com.microservices_example_app.users.model.Role;
import com.microservices_example_app.users.repository.RoleRepository;
import com.microservices_example_app.users.service.UserService;
import com.microservices_example_app.users.util.SensitiveMask;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Email;
import lombok.AllArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.extern.slf4j.Slf4j;

import java.util.List;

@Slf4j
@AllArgsConstructor
@RestController
@RequestMapping("/users/auth")
@Validated
@Tag(name = "Authentication", description = "User registration, login and password recovery")
public class AuthenticationController {
    private UserService userService;
    private RoleRepository roleDao;


    @Operation(summary = "Request a password-reset email")
    @PostMapping("/forget-password")
    public ResponseEntity<Void> forgetPassword(@Parameter(description = "Account email address") @RequestParam @Email String email){
         userService.restorePassword(email);
        return ResponseEntity.ok().build();
    }

    @Operation(summary = "Reset password with a one-time token")
    @PostMapping("/reset-password")
    public ResponseEntity<Void> resetPassword(@Valid @RequestBody PasswordResetRequestDto request) {
        log.info("Password reset request with token");
        userService.resetPassword(request.getToken(), request.getNewPassword());
        return ResponseEntity.ok().build();
    }

    @Operation(summary = "Register a new user")
    @PostMapping("/register")
    public ResponseEntity<UserRegistrationDto> register(@Valid @RequestBody UserRegistrationRequestDto request) {
        log.info("                 REGISTRATION REQUEST RECEIVED                 ");
        log.info("Registration attempt for email: {}", SensitiveMask.maskEmail(request.getEmail()));
        log.info("Request details - username: {}, role: {}", request.getUsername(), request.getRole());

        UserRegistrationDto response = userService.register(
                request.getEmail(),
                request.getPassword(),
                request.getRole(),
                request.getUsername(),
                false
        );
        log.info("Registration successful for email: {}", SensitiveMask.maskEmail(request.getEmail()));
        return ResponseEntity.ok(response);
    }

    @Operation(summary = "Authenticate and obtain a JWT")
    @PostMapping("/login")
    public ResponseEntity<UserLoginResponseDto> login(@Valid @RequestBody UserLoginRequestDto request) {
        log.info("                 LOGIN REQUEST RECEIVED                 ");
        log.info("Login attempt for email: {}", SensitiveMask.maskEmail(request.getEmail()));
        return ResponseEntity.ok(userService.login(request.getEmail(), request.getPassword()));
    }
    @Operation(summary = "List all available roles")
    @GetMapping("/roles")
    public List<Role> getRoles(){
        return roleDao.findAll();
    }

    @Operation(summary = "Check whether a password-reset token is still valid")
    @GetMapping("/validate-reset-token")
    public boolean validateResetToken(@Parameter(description = "One-time reset token") @RequestParam String token) {
        return userService.validateResetToken(token);
    }
}
