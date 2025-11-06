package fr.leuwen.rhdemoAPI;

import static org.hamcrest.CoreMatchers.is;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.security.test.context.support.WithMockUser;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;

//Config test unitaire 
//@WebMvcTest (controllers=EmployeController.class)

// Config test intégration
@SpringBootTest
@TestPropertySource(locations = "classpath:application-test.properties")
@AutoConfigureMockMvc
@ActiveProfiles("test") // Active le profil "test" pour utiliser TestSecurityConfig
public class EmployeControllerTest {
	
	@Autowired
	private MockMvc mockMVC;
	
	// Config test unitaire
	//@MockitoBean
	//private EmployeService employeService;
	
	
	@Test
	@WithMockUser(username = "UtilisateurTest", roles = {"Mauvais role"})
	public void testGetEmployesRoleErrone() throws Exception {
		mockMVC.perform(get("/api/employes"))
		.andExpect(status().is4xxClientError());
	}
	
	
	@Test
	@WithMockUser(username = "UtilisateurTest", roles = {"consult"})
	public void testGetEmployes() throws Exception {
		mockMVC.perform(get("/api/employes"))
		.andExpect(status().isOk())
		//Test intégration uniquement
		.andExpect(jsonPath("$").isArray())
		.andExpect(jsonPath("$.length()").value(4)) // On attend 4 employés du data.sql
		//première ligne du résultat, champ prenom
		.andExpect(jsonPath("$[0].prenom", is("Laurent")));
	}
	
}
