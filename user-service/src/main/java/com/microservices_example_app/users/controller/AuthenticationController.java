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
import org.springframework.web.bind.annotation.*;
import lombok.extern.slf4j.Slf4j;

import java.util.List;

@Slf4j
@AllArgsConstructor
@RestController
@RequestMapping("/users/auth")
public class AuthenticationController {
    private UserService userService;
    private RoleRepository roleDao;


    @GetMapping("/forget-password")
    public int forgetPassword(@RequestParam @Email String email){
         userService.restorePassword(email);
        return HttpServletResponse.SC_OK;
    }

    @PostMapping("/reset-password")
    public void resetPassword(@RequestParam String token, @RequestParam String newPassword) {
        log.info("Password reset request with token");
        userService.resetPassword(token, newPassword);
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
                request.getUsername()
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
