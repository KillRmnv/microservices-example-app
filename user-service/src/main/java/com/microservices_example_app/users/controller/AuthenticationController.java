package com.microservices_example_app.users.controller;

import com.microservices_example_app.users.dto.*;
import com.microservices_example_app.users.model.Role;
import com.microservices_example_app.users.repository.RoleRepository;
import com.microservices_example_app.users.service.UserService;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.constraints.Email;
import lombok.AllArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@AllArgsConstructor
@RestController("/users/auth")
public class AuthenticationController {
    private UserService userService;
    private RoleRepository roleDao;


    @GetMapping("/forget-password")
    public PasswordRestoringResponse forgetPassword(@RequestParam @Email String email){
        return userService.restorePassword(email);
    }

    @PostMapping("/register")
    public ResponseEntity<UserRegistrationDto> register(@RequestBody UserRegistrationRequestDto request) {
        UserRegistrationDto response = userService.register(
                request.getEmail(),
                request.getPassword(),
                request.getRole(),
                request.getUsername()
        );
        return ResponseEntity.ok(response);
    }

    @PostMapping("/login")
    public ResponseEntity<UserLoginResponseDto> login(@RequestBody UserLoginRequestDto request) {
        return ResponseEntity.ok(userService.login(request.getEmail(), request.getPassword()));
    }
    @GetMapping("/roles")
    public List<Role> getRoles(){
        return roleDao.findAll();
    }
}
