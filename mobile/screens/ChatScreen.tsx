import { useState } from "react";
import { View, Text, TextInput, Button, StyleSheet } from "react-native";
import { routeEnvelope } from "../utils/envelopeRouter";
import { API_BASE } from "../constants";
import { getDeviceId } from "../utils/deviceId";
import { getCurrentLocation } from "../utils/location";

export default function ChatScreen({ navigation, route }: any) {
    const { payload, meta, session_id, __history_text, profile } = route.params;
    const [answer, setAnswer] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const q = payload.question;

    async function sendAnswer() {
        if (!answer.trim()) return;
        setError(null);
        setLoading(true);
        try {
            const combinedText = `${__history_text}\nQ:${q.text}\nA:${answer}`;
            const location = await getCurrentLocation();
            const body: Record<string, unknown> = {
                session_id,
                locale: "tr-TR",
                user_message: answer,
                profile: profile ?? null,
            };
            if (location) {
                body.lat = location.lat;
                body.lon = location.lon;
            }

            const res = await fetch(`${API_BASE}/v1/triage/turn`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "x-device-id": getDeviceId(),
                },
                body: JSON.stringify(body),
            });

            if (res.status === 429) {
                let resetSec = 60;
                const resetHeader = res.headers.get("X-RateLimit-Reset");
                if (resetHeader) resetSec = parseInt(resetHeader, 10) || 60;
                else {
                    try {
                        const data = await res.json();
                        if (typeof data?.reset_in_sec === "number") resetSec = data.reset_in_sec;
                    } catch {
                        /* ignore */
                    }
                }
                setError(`Çok fazla istek. ${resetSec} saniye sonra tekrar deneyin.`);
                setLoading(false);
                return;
            }

            const env = await res.json();
            const next = routeEnvelope(env);
            const nextSessionId = env?.session_id ?? session_id;

            navigation.navigate(next.screen, {
                ...next.params,
                session_id: nextSessionId,
                __history_text: combinedText,
                profile: profile ?? null,
            });
        } catch {
            setError("Bağlantı hatası. Lütfen tekrar deneyin.");
        } finally {
            setLoading(false);
        }
    }

    return (
        <View style={styles.container}>
            {meta?.same_day && (
                <View style={styles.sameDayBanner}>
                    <Text style={styles.sameDayTitle}>Bugün kontrol önerisi</Text>
                    <Text style={styles.sameDayText}>{meta.same_day.message}</Text>
                </View>
            )}

            <Text style={styles.question} accessibilityRole="header">{q.text}</Text>

            <Text style={styles.label}>Cevabını yaz:</Text>
            <TextInput
                value={answer}
                onChangeText={setAnswer}
                placeholder="Cevabın..."
                multiline
                style={styles.input}
                editable={!loading}
                accessibilityLabel="Cevap"
                accessibilityHint="Soruyu yanıtlayın"
            />

            {error ? (
                <View style={styles.errorBox} accessibilityRole="alert">
                    <Text style={styles.errorText}>{error}</Text>
                    <Button title="Tekrar dene" onPress={sendAnswer} disabled={loading} accessibilityLabel="Tekrar dene" accessibilityHint="Cevabı yeniden gönderir" />
                </View>
            ) : null}

            <Button title={loading ? "Gönderiliyor..." : "Gönder"} onPress={sendAnswer} disabled={!answer.trim() || loading} accessibilityLabel={loading ? "Gönderiliyor" : "Gönder"} accessibilityHint="Cevabı gönderir" />
        </View>
    );
}

const styles = StyleSheet.create({
    container: {
        padding: 16,
        gap: 12,
        flex: 1,
        backgroundColor: "#fff",
    },
    sameDayBanner: {
        padding: 12,
        borderRadius: 12,
        borderWidth: 1,
        borderColor: "#f59e0b",
        backgroundColor: "#fef3c7",
    },
    sameDayTitle: {
        fontWeight: "700",
        color: "#92400e",
        marginBottom: 4,
    },
    sameDayText: {
        color: "#92400e",
        fontSize: 14,
    },
    question: {
        fontSize: 18,
        fontWeight: "700",
        marginTop: 12,
    },
    label: {
        fontSize: 14,
        fontWeight: "600",
        marginTop: 8,
    },
    input: {
        borderWidth: 1,
        borderColor: "#ddd",
        borderRadius: 12,
        padding: 12,
        minHeight: 100,
        fontSize: 16,
        textAlignVertical: "top",
    },
    errorBox: {
        padding: 12,
        backgroundColor: "#fef2f2",
        borderRadius: 12,
        borderWidth: 1,
        borderColor: "#fecaca",
    },
    errorText: {
        fontSize: 14,
        color: "#991b1b",
        marginBottom: 8,
    },
});
