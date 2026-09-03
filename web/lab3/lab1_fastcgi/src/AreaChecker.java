public class AreaChecker {

    /**
     * Дефолтная валидация
     */
    public static void validate(double x, double y, double r) {
        if (r <= 0) {
            throw new IllegalArgumentException("Радиус R должен быть строго больше нуля");
        }
    }

    /**
     * Чекаем по области
     * TODO: чекаем по варику, что там будет нужно в итоге
     */
    public static boolean isInside(double x, double y, double r) {
        return true;
    }
}
