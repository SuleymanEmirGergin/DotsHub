import { useState } from "react";
import { View, Text, TextInput, Button, StyleSheet, Alert } from "react-native";
import { routeEnvelope } from "../utils/envelopeRouter";
import { API_BASE } from "../constants";

export default function ChatScreen({ navigation, route }: any) {
    const { payload, meta, session_id, __history_text, profile } = route.params;
    const [answer, setAnswer] = useState("");
    const [loading, setLoading] = useState(false);

    const q = payload.question;

    async function sendAnswer() {
        if (!answer.trim()) return;

        setLoading(true);
        try {
            const combinedText = `${__history_text}\nQ:${q.text}\nA:${answer}`;

            const res = await fetch(`${API_BASE}/v1/triage/turn`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "x-device-id": "DEVICE_ID_HERE",
                },
                body: JSON.stringify({
                    session_id,
                    locale: "tr-TR",
                    user_message: answer,
                    profile: profile ?? null,
                }),
            });

            const env = await res.json();
            const next = routeEnvelope(env);
            const nextSessionId = env?.session_id ?? session_id;

            navigation.navigate(next.screen, {
                ...next.params,
                session_id: nextSessionId,
                __history_text: combinedText,
                profile: profile ?? null,
            });
        } catch (error) {
            Alert.alert("Hata", String(error));
        } finally {
            setLoading(false);
        }
    }

    return (
        <View style={styles.container}>
            {meta?.same_day && (
                <View style={styles.sameDayBanner}>
                    <Text style={styles.sameDayTitle}>Bugun kontrol onerisi</Text>
                    <Text style={styles.sameDayText}>{meta.same_day.message}</Text>
                </View>
            )}

            <Text style={styles.question}>{q.text}</Text>

            <Text style={styles.label}>Cevabini yaz:</Text>
            <TextInput
                value={answer}
                onChangeText={setAnswer}
                placeholder="Cevabin..."
                multiline
                style={styles.input}
                editable={!loading}
            />

            <Button title={loading ? "Gonderiliyor..." : "Gonder"} onPress={sendAnswer} disabled={!answer.trim() || loading} />
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
});
