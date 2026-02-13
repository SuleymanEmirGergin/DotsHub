import { useState } from "react";
import { View, TextInput, Button, Text, StyleSheet, Switch } from "react-native";
import { routeEnvelope } from "../utils/envelopeRouter";
import { API_BASE } from "../constants";
import { getDeviceId } from "../utils/deviceId";
import { getCurrentLocation } from "../utils/location";

export default function HomeScreen({ navigation }: any) {
    const [text, setText] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [age, setAge] = useState("");
    const [pregnantEnabled, setPregnantEnabled] = useState(false);
    const [pregnant, setPregnant] = useState(false);

    async function submit() {
        if (!text.trim()) return;
        setError(null);
        setLoading(true);
        try {
            const profile = {
                age: age ? Number(age) : null,
                pregnant: pregnantEnabled ? pregnant : null,
            };
            const location = await getCurrentLocation();
            const body: Record<string, unknown> = {
                session_id: null,
                locale: "tr-TR",
                user_message: text,
                profile,
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
            const nextSessionId = env?.session_id ?? null;

            navigation.navigate(next.screen, {
                ...next.params,
                session_id: nextSessionId,
                __history_text: text,
                profile,
            });
        } catch (err) {
            setError("Bağlantı hatası. Lütfen tekrar deneyin.");
        } finally {
            setLoading(false);
        }
    }

    return (
        <View style={styles.container} accessibilityRole="form">
            <Text style={styles.title} accessibilityRole="header">Semptomlarını Yaz</Text>
            <Text style={styles.subtitle} accessibilityLabel="Bu uygulama tıbbi teşhis yerine geçmez.">Bu uygulama tıbbi teşhis yerine geçmez.</Text>

            <TextInput
                value={text}
                onChangeText={setText}
                placeholder="Örn: 3 gündür boğazım ağrıyor, ateşim var..."
                multiline
                style={styles.input}
                editable={!loading}
                accessibilityLabel="Semptom açıklaması"
                accessibilityHint="Belirtilerinizi kısaca yazın"
            />

            <Text style={styles.locationHint}>Konum izni verirseniz, sonuç ekranında size yakın sağlık kuruluşları gösterilir. İsteğe bağlıdır.</Text>
            <Text style={styles.optionalLabel}>Opsiyonel profil</Text>
            <TextInput
                value={age}
                onChangeText={setAge}
                placeholder="Yaş (opsiyonel)"
                keyboardType="number-pad"
                style={styles.inputMini}
                editable={!loading}
                accessibilityLabel="Yaş, opsiyonel"
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

            {error ? (
                <View style={styles.errorBox} accessibilityRole="alert">
                    <Text style={styles.errorText}>{error}</Text>
                    <Button title="Tekrar dene" onPress={submit} disabled={loading} accessibilityLabel="Tekrar dene" accessibilityHint="İsteği yeniden gönderir" />
                </View>
            ) : null}

            <Button title={loading ? "Değerlendiriliyor..." : "Devam"} onPress={submit} accessibilityLabel={loading ? "Değerlendiriliyor" : "Devam"} accessibilityHint="Semptomları gönderir" disabled={!text.trim() || loading} />
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
    locationHint: {
        fontSize: 12,
        opacity: 0.8,
        marginTop: 8,
        color: "#555",
        fontStyle: "italic",
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
