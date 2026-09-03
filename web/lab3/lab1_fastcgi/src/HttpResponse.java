import java.io.IOException;
import java.nio.charset.StandardCharsets;

public class HttpResponse {
    /**
     * Отправка сообщений о внутренней системной ошибки сервера (500)
     */
    public static void sendSystemError(String message) throws IOException {
        String jsonError = String.format("{\"error\":\"Критический сбой сервера: %s\"}", message.replace("\"", "\\\""));

        byte[] bytes = jsonError.getBytes(StandardCharsets.UTF_8);

        String response =
                "Status: 500 Internal Server Error\n" +
                        "Content-Type: application/json; charset=utf-8\n" +
                        "Content-Length: " + bytes.length + "\n\n" +
                        jsonError;
        System.out.print(response);
        System.out.flush();
    }

    /**
     * Отправка JSON данных по HTTP
     */
    public static void sendJson(String json) throws IOException {
        byte[] bytes = json.getBytes(StandardCharsets.UTF_8);

        String response = "Status: 200 OK\n" +
                "Content-Type: application/json; charset=utf-8\n" +
                "Content-Length: " + bytes.length + "\n\n" +
                json;
        System.out.print(response);
        System.out.flush();
    }

    /**
     * Отправка сообщений при ошибки валидации (400)
     */
    public static void sendError(String message) throws IOException {
        String jsonError = String.format("{\"error\":\"%s\"}", message.replace("\"", "\\\"")); //последняя шутка, чтобы экранировать кавычки и дсон не здох в итоге
        byte[] bytes = jsonError.getBytes(StandardCharsets.UTF_8);

        String response =
                "Status: 400 Bad Request\n" +
                        "Content-Type: application/json; charset=utf-8\n" +
                        "Content-Length: " + bytes.length + "\n\n" +
                        jsonError;

        System.out.print(response);
        System.out.flush();
    }
}
