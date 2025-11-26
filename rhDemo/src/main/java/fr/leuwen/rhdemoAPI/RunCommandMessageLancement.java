package fr.leuwen.rhdemoAPI;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@Component
public class RunCommandMessageLancement implements CommandLineRunner {

	@Value("${fr.leuwen.rhdemoAPI.messagelancement}")
	private String ml;
	private static final Logger logger = LoggerFactory.getLogger(RunCommandMessageLancement.class);

	@Override
	public void run(String... args) throws Exception {
		logger.info(ml);
	}

}
