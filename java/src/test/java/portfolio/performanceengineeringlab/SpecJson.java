package portfolio.performanceengineeringlab;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Minimal JSON reader for spec/experiments.json in tests (objects, arrays, strings, numbers, booleans). */
public final class SpecJson {
    private final String s;
    private int i;

    private SpecJson(String s) {
        this.s = s;
    }

    /** The decoded spec named by the spec.path system property (set by surefire). */
    @SuppressWarnings("unchecked")
    public static Map<String, Object> load() {
        try {
            String path = System.getProperty("spec.path", "../spec/experiments.json");
            String text = Files.readString(Path.of(path), StandardCharsets.UTF_8);
            SpecJson p = new SpecJson(text);
            Object v = p.value();
            p.ws();
            if (p.i != text.length()) {
                throw new IllegalStateException("trailing data at " + p.i);
            }
            return (Map<String, Object>) v;
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
    }

    /** Navigates nested objects and arrays by key or index. */
    public static Object at(Object root, Object... path) {
        Object cur = root;
        for (Object p : path) {
            cur = p instanceof Integer idx ? ((List<?>) cur).get(idx) : ((Map<?, ?>) cur).get(p);
        }
        return cur;
    }

    /** Skips whitespace. */
    private void ws() {
        while (i < s.length() && Character.isWhitespace(s.charAt(i))) {
            i++;
        }
    }

    /** Parses any value. */
    private Object value() {
        ws();
        char c = s.charAt(i);
        if (c == '{') {
            return object();
        }
        if (c == '[') {
            return array();
        }
        if (c == '"') {
            return string();
        }
        if (s.startsWith("true", i) || s.startsWith("false", i) || s.startsWith("null", i)) {
            String word = s.startsWith("true", i) ? "true" : s.startsWith("false", i) ? "false" : "null";
            i += word.length();
            return word.equals("null") ? null : Boolean.valueOf(word);
        }
        return number();
    }

    /** Parses an object. */
    private Map<String, Object> object() {
        Map<String, Object> out = new LinkedHashMap<>();
        i++;
        ws();
        if (s.charAt(i) == '}') {
            i++;
            return out;
        }
        while (true) {
            ws();
            String key = string();
            ws();
            expect(':');
            out.put(key, value());
            ws();
            if (s.charAt(i) == ',') {
                i++;
            } else {
                expect('}');
                return out;
            }
        }
    }

    /** Parses an array. */
    private List<Object> array() {
        List<Object> out = new ArrayList<>();
        i++;
        ws();
        if (s.charAt(i) == ']') {
            i++;
            return out;
        }
        while (true) {
            out.add(value());
            ws();
            if (s.charAt(i) == ',') {
                i++;
            } else {
                expect(']');
                return out;
            }
        }
    }

    /** Parses a string (escapes limited to what the spec uses). */
    private String string() {
        expect('"');
        StringBuilder b = new StringBuilder();
        while (s.charAt(i) != '"') {
            char c = s.charAt(i++);
            if (c == '\\') {
                b.append(s.charAt(i++));
            } else {
                b.append(c);
            }
        }
        i++;
        return b.toString();
    }

    /** Parses a number as Long when integral, else Double. */
    private Object number() {
        int start = i;
        while (i < s.length() && "+-0123456789.eE".indexOf(s.charAt(i)) >= 0) {
            i++;
        }
        String t = s.substring(start, i);
        if (t.isEmpty()) {
            throw new IllegalStateException("unexpected character at " + start);
        }
        // Not a ternary: `c ? Double : Long` would unbox both and promote the Long to double.
        if (t.contains(".") || t.contains("e") || t.contains("E")) {
            return Double.valueOf(t);
        }
        return Long.valueOf(t);
    }

    /** Consumes one expected character. */
    private void expect(char c) {
        if (s.charAt(i) != c) {
            throw new IllegalStateException("expected '" + c + "' at " + i);
        }
        i++;
    }
}
