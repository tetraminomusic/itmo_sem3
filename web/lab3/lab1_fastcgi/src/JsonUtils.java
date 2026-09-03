import java.util.Locale;
import java.util.concurrent.CopyOnWriteArrayList;

public class JsonUtils {

    public static String buildResponseJson(String currentResult, CopyOnWriteArrayList<String> history) {
        StringBuilder sb = new StringBuilder();

        sb.append("{");
        sb.append("\"current\":").append(currentResult).append(",");
        sb.append("\"history\":[");
        for (int i = 0; i < history.size(); i++) {
            sb.append(history.get(i));
            if (i < history.size() - 1) {
                sb.append(",");
            }
        }
        sb.append("]");
        sb.append("}");
        return sb.toString();
    }

    public static String formatSystemError(String message) {
        return String.format("{\"error\":\"Критический сбой сервера: %s\"}", message.replace("\"", "\\\""));
    }

    public static String formatError(String message) {
        return String.format("{\"error\":\"%s\"}", message.replace("\"", "\\\""));
    }

    public static String formatResult(double x, double y, double r, boolean isInside, String currentTime, double executionTimeMs) {
        return String.format(
                Locale.US,
                "{\"x\":%.4f,\"y\":%.4f,\"r\":%.4f,\"inside\":%b,\"currentTime\":\"%s\",\"executionTimeMs\":%.4f}",
                x, y, r, isInside, currentTime, executionTimeMs
        );
    }


}
