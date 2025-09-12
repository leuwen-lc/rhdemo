package fr.leuwen.rhdemoAPI.service;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;


@Component
public class GenereMessageLancement {

@Value("${fr.leuwen.rhdemoAPI.messagelancement}")
private String ml;

public String donnerMessageLancement () { 
return ml;
}
}
