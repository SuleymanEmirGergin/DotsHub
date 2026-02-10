import { useState } from "react";
import { View, TextInput, Button, Text, StyleSheet, Switch, Alert } from "react-native";
import { routeEnvelope } from "../utils/envelopeRouter";
import { API_BASE } from "../constants";

export default function HomeScreen({ navigation }: any) {
    const [text, setText] = useState("");
    const [loading, setLoading] = useState(false);
    const [age, setAge] = useState("");
    const [pregnantEnabled, setPregnantEnabled] = useState(false);
    const [pregnant, setPregnant] = useState(false);

    async function submit() {
        if (!text.trim()) return;

        setLoading(true);
        try {
            const profile = {
                age: age ? Number(age) : null,
                pregnant: pregnantEnabled ? pregnant : null,
            };

            const res = await fetch(`${API_BASE}/v1/triage/turn`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "x-device-id": "DEVICE_ID_HERE", // TODO: get from device
                },
                body: JSON.stringify({
                    session_id: null,
                    locale: "tr-TR",
                    user_message: text,
                    profile,
                }),
            });

            const env = await res.json();
            const next = routeEnvelope(env);
            const nextSessionId = env?.session_id ?? null;

            navigation.navigate(next.screen, {
                ...next.params,
                session_id: nextSessionId,
                __history_text: text,
                profile,
            });
        } catch (error) {
            Alert.alert("Hata", "Hata olustu: " + String(error));
        } finally {
            setLoading(false);
        }
    }

    return (
        <View style={styles.container}>
            <Text style={styles.title}>Semptomlarini Yaz</Text>
            <Text style={styles.subtitle}>Bu uygulama tibbi teshis yerine gecmez.</Text>

            <TextInput
                value={text}
                onChangeText={setText}
                placeholder="Orn: 3 gundur bogazim agriyor, atesim var..."
                multiline
                style={styles.input}
                editable={!loading}
            />

            <Text style={styles.optionalLabel}>Opsiyonel profil</Text>
            <TextInput
                value={age}
                onChangeText={setAge}
                placeholder="Yas (opsiyonel)"
                keyboardType="number-pad"
                style={styles.inputMini}
                editable={!loading}
            />
            <View style={styles.row}>
                <Text style={styles.rowText}>Pregnancy info</Text>
                <Switch value={pregnantEnabled} onValueChange={setPregnantEnabled} disabled={loading} />
            </View>
            {pregnantEnabled ? (
                <View style={styles.row}>
                    <Text style={styles.rowText}>Pregnant</Text>
                    <Switch value={pregnant} onValueChange={setPregnant} disabled={loading} />
                </View>
            ) : null}

            <Button title={loading ? "Degerlendiriliyor..." : "Devam"} onPress={submit} disabled={!text.trim() || loading} />
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
    title: {
        fontSize: 24,
        fontWeight: "700",
        marginTop: 20,
    },
    subtitle: {
        opacity: 0.7,
        fontSize: 14,
    },
    input: {
        borderWidth: 1,
        borderColor: "#ddd",
        borderRadius: 12,
        padding: 12,
        minHeight: 120,
        fontSize: 16,
        textAlignVertical: "top",
    },
    optionalLabel: {
        fontSize: 13,
        opacity: 0.7,
        marginTop: 4,
    },
    inputMini: {
        borderWidth: 1,
        borderColor: "#ddd",
        borderRadius: 12,
        padding: 12,
        fontSize: 15,
    },
    row: {
        flexDirection: "row",
        alignItems: "center",
        justifyContent: "space-between",
        paddingVertical: 2,
    },
    rowText: {
        fontSize: 14,
    },
});
