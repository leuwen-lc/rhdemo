package fr.leuwen.rhdemoAPI;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import fr.leuwen.rhdemoAPI.service.GenereMessageLancement;

@Component
public class RunCommandMessageLancement implements CommandLineRunner {

	@Autowired
	private GenereMessageLancement gml;
	private static final Logger logger = LoggerFactory.getLogger(RunCommandMessageLancement.class);

	@Override
	public void run(String... args) throws Exception {
		logger.info(gml.donnerMessageLancement());

	}

}
