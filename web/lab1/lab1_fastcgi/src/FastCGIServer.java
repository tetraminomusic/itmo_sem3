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

                String queryString = System.getProperty("QUERY_STRING");

                if (queryString == null || queryString.isEmpty()) {
                    HttpResponse.sendError("Отсутствуют входные параметры в URL");
                    continue;
                }

                Map<String, String> params = parseQueryString(queryString);
                String xStr = params.get("x");
                String yStr = params.get("y");
                String rStr = params.get("r");

                if (xStr == null || yStr == null || rStr == null) {
                    HttpResponse.sendError("Пропущены какие-то параметры");
                    continue;
                }

                double x = Double.parseDouble(xStr.replace(",","."));
                double y = Double.parseDouble(yStr.replace(",","."));
                double r = Double.parseDouble(rStr.replace(",","."));

                AreaChecker.validate(x,y,r);

                processAndSendResponse(x,y,r,startTime);
            } catch (IllegalArgumentException e) {
                /**
                 * Обработка ошибки, если заместо чисел в коордах пришли буковки
                 */
                String errorMsg;
                if (e instanceof NumberFormatException) {
                    errorMsg = "Параметры X, Y и R должны быть валидными числами.";
                } else {
                    errorMsg = e.getMessage();
                }
                System.err.println("Ошибка валидации: " + errorMsg);
                try {
                    HttpResponse.sendError("Ошибка валидации: коорды долдны быть числами");
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
                    HttpResponse.sendSystemError("Внутренняя ошибка сервера (NullPointer).");
                } catch (IOException ignored) {}
            } catch (Exception e) {
                /**
                 * Всё остальное
                 */

                System.err.println("Исключение: " + e.getClass().getName() + " - " + e.getMessage());
                try {
                    HttpResponse.sendSystemError("Внутренняя ошибка сервера: " + e.getMessage());
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
                        "Content-Length: " + contentBytes.length +
                        "\n\n" +
                        content;

        System.out.print(httpResponse);

        //отправляем данные сразу, чоб нет
        System.out.flush();
    }

    /**
     * Парсим сроку запроса
     */
    private static Map<String, String> parseQueryString(String query) {
        Map<String, String> params = new HashMap<>();

        //если ничё не пришло
        if (query == null || query.isEmpty()) {
            return params;
        }

        //дробление
        String[] pairs = query.split("&");

        for (String pair: pairs) {
            int idx = pair.indexOf("=");
            if (idx > 0 && idx < pair.length() - 1) {
                //получаем ключ
                String key = pair.substring(0,idx);
                //получаем значение
                String value = pair.substring(idx+1);

                params.put(key, value);
            }
        }

        return params;
    }

    private static void processAndSendResponse(double x, double y, double r, long startTime) throws IOException {
        boolean isInside = AreaChecker.isInside(x,y,r);

        long endTime = System.nanoTime();
        double executionTimeMs = (endTime - startTime) / 1_000_000.0;
        String currentTime = LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"));

        String currentJson = JsonUtils.formatResult(x, y, r, isInside, currentTime, executionTimeMs);

        history.add(currentJson);

        String responseJson = JsonUtils.buildResponseJson(currentJson, history);

        HttpResponse.sendJson(responseJson);
    }
}
