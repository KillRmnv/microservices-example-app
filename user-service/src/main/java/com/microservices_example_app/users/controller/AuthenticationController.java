package com.microservices_example_app.users.controller;

import com.microservices_example_app.users.dto.*;
import com.microservices_example_app.users.model.Role;
import com.microservices_example_app.users.repository.RoleRepository;
import com.microservices_example_app.users.service.UserService;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Email;
import lombok.AllArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;
import lombok.extern.slf4j.Slf4j;

import java.util.List;

@Slf4j
@AllArgsConstructor
@RestController
@RequestMapping("/users/auth")
@Validated
public class AuthenticationController {
    private UserService userService;
    private RoleRepository roleDao;


    @PostMapping("/forget-password")
    public ResponseEntity<Void> forgetPassword(@RequestParam @Email String email){
         userService.restorePassword(email);
        return ResponseEntity.ok().build();
    }

    @PostMapping("/reset-password")
    public ResponseEntity<Void> resetPassword(@Valid @RequestBody PasswordResetRequestDto request) {
        log.info("Password reset request with token");
        userService.resetPassword(request.getToken(), request.getNewPassword());
        return ResponseEntity.ok().build();
    }

    @PostMapping("/register")
    public ResponseEntity<UserRegistrationDto> register(@Valid @RequestBody UserRegistrationRequestDto request) {
        log.info("                 REGISTRATION REQUEST RECEIVED                 ");
        log.info("Registration attempt for email: {}", request.getEmail());
        log.info("Request details - username: {}, role: {}", request.getUsername(), request.getRole());

        UserRegistrationDto response = userService.register(
                request.getEmail(),
                request.getPassword(),
                request.getRole(),
                request.getUsername(),
                false
        );
        log.info("Registration successful for email: {}", request.getEmail());
        return ResponseEntity.ok(response);
    }

    @PostMapping("/login")
    public ResponseEntity<UserLoginResponseDto> login(@Valid @RequestBody UserLoginRequestDto request) {
        log.info("                 LOGIN REQUEST RECEIVED                 ");
        log.info("Login attempt for email: {}", request.getEmail());
        return ResponseEntity.ok(userService.login(request.getEmail(), request.getPassword()));
    }
    @GetMapping("/roles")
    public List<Role> getRoles(){
        return roleDao.findAll();
    }

    @GetMapping("/validate-reset-token")
    public boolean validateResetToken(@RequestParam String token) {
        return userService.validateResetToken(token);
    }
}
