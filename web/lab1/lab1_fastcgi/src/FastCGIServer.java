import com.fastcgi.FCGIInterface;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.CopyOnWriteArrayList;

public class FastCGIServer {
    /**
     * История
     */
    private static final CopyOnWriteArrayList<String> history = new CopyOnWriteArrayList<>();

    public static void main (String[] args) {
        FCGIInterface fcgiInterface = new FCGIInterface();

        while (fcgiInterface.FCGIaccept() >= 0) {

            long startTime = System.nanoTime();

            try {
                sendTestResponse("Абоба");
            } catch (NumberFormatException e) {
                /**
                 * Обработка ошибки, если заместо чисел в коордах пришли буковки
                 */

                System.err.println("Клиент прислал неверный формат чисел: " + e.getMessage());
                try {
                    sendError("Ошибка валидации: коорды долдны быть числами");
                } catch (IOException ignored) {}
            } catch (IOException e) {
                /**
                 * Обработка ошибки, если произошёл разрыв при записи в поток вывода
                 */

                System.err.println("Сетевой сбой при общении с веб-сервером: " + e.getMessage());
            } catch (NullPointerException e) {
                /**
                 * На всякий пожарный, если в коде будут косяки
                 */

                System.err.println("Ошибка NullPointerException на сервере");
                e.printStackTrace();
                try { //логи
                    sendSystemError("Внутренняя ошибка сервера (NullPointer).");
                } catch (IOException ignored) {}
            } catch (Exception e) {
                /**
                 * Всё остальное
                 */

                System.err.println("Исключение: " + e.getClass().getName() + " - " + e.getMessage());
                try {
                    sendSystemError("Внутренняя ошибка сервера: " + e.getMessage());
                } catch (IOException ignored) {}
            }
        }
    }

    /**
     * Отправка простого текстового ответа (берем дефолтный текст и отправяет как http запрос)
     * 200
     */
    private static void sendTestResponse(String content) throws IOException {
        byte[] contentBytes = content.getBytes(StandardCharsets.UTF_8);

        String httpResponse =
                "Status: 200 OK\n" +
                        "Content-Type: text/plain; charset=utf-8\n" +
                        "Content-Length: " + contentBytes +
                        "\n\n" +
                        content;

        System.out.print(httpResponse);

        //отправляем данные сразу, чоб нет
        System.out.flush();
    }

    /**
     * Отправка сообщений при ошибки валидации (400)
     */
    private static void sendError(String message) throws IOException {
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

    /**
     * Отправка сообщений о внутренней системной ошибки сервера (500)
     */
    private static void sendSystemError(String message) throws IOException {
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


}
