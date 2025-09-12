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
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;

//Config test unitaire 
//@WebMvcTest (controllers=EmployeController.class)

// Config test intégration
@SpringBootTest
@TestPropertySource(locations = "classpath:application-test.properties")
@AutoConfigureMockMvc
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
	@WithMockUser(username = "UtilisateurTest", roles = {"Consult"})
	public void testGetEmployes() throws Exception {
		mockMVC.perform(get("/api/employes"))
		.andExpect(status().isOk())
		//Test intégration uniquement
		//première ligne du résultat, champ firstName
		.andExpect(jsonPath("$[0].prenom", is("Laurent")));
	}
	
}
