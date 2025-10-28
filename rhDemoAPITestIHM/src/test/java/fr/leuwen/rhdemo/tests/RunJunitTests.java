package fr.leuwen.rhdemo.tests;
import org.junit.platform.launcher.Launcher;
import org.junit.platform.launcher.LauncherDiscoveryRequest;
import org.junit.platform.launcher.core.LauncherDiscoveryRequestBuilder;
import org.junit.platform.launcher.core.LauncherFactory;
import org.junit.platform.engine.discovery.DiscoverySelectors;

public class RunJunitTests {
    public static void main(String[] args) {
        LauncherDiscoveryRequest request = LauncherDiscoveryRequestBuilder.request()
            .selectors(
                DiscoverySelectors.selectClass(EmployeLifecycleTest.class) // Mets ici ta classe de test
            )
            .build();

        Launcher launcher = LauncherFactory.create();
        launcher.execute(request);
    }
}