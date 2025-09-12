package fr.leuwen.rhdemoAPI;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;

import fr.leuwen.rhdemoAPI.service.GenereMessageLancement;

@Component
public class RunCommandMessageLancement implements CommandLineRunner {

	@Autowired
	private GenereMessageLancement gml;
	@Override
	public void run(String... args) throws Exception {
		System.out.println(gml.donnerMessageLancement());

	}

}
