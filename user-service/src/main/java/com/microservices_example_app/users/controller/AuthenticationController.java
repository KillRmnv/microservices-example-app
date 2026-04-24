package com.microservices_example_app.users.controller;

import com.microservices_example_app.users.dto.PasswordRestoringResponse;
import com.microservices_example_app.users.dto.UserLoginResponseDto;
import com.microservices_example_app.users.model.Role;
import com.microservices_example_app.users.repository.RoleRepository;
import com.microservices_example_app.users.service.UserService;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.constraints.Email;
import lombok.AllArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@AllArgsConstructor
@RestController("/users/auth")
public class AuthenticationController {
    private UserService userService;
    private RoleRepository roleDao;

    @GetMapping("/login/by-email")
    public UserLoginResponseDto login(@RequestParam @Email String email,@RequestParam String password){
       return  userService.login(email,password);
    }
    @GetMapping("/forget-password")
    public PasswordRestoringResponse forgetPassword(@RequestParam @Email String email){
        return userService.restorePassword(email);
    }

    @PostMapping("/register")
    public int register(@RequestParam @Email String email,
                        @RequestParam String password,
                        @RequestParam String username,
                        @RequestParam String role) {
        userService.register(email, password, role, username);
        return HttpServletResponse.SC_CREATED;
    }
    @GetMapping("/roles")
    public List<Role> getRoles(){
        return roleDao.findAll();
    }
}
