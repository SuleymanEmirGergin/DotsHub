import { View, Text, Button, StyleSheet, ScrollView, Alert } from "react-native";

import { API_BASE } from "../constants";

function riskColor(level?: string): string {
    if (level === "HIGH") return "#dc2626";
    if (level === "MEDIUM") return "#d97706";
    return "#059669";
}

function riskBg(level?: string): string {
    if (level === "HIGH") return "#fef2f2";
    if (level === "MEDIUM") return "#fffbeb";
    return "#ecfdf5";
}

export default function ResultScreen({ route, navigation }: any) {
    const { payload, meta, stop_reason, session_id } = route.params;

    async function sendFeedback(rating: 1 | -1) {
        try {
            await fetch(`${API_BASE}/v1/triage/feedback`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    session_id,
                    rating: rating === 1 ? "up" : "down",
                    comment: null,
                    user_selected_specialty_id: null,
                }),
            });
            Alert.alert("Geri Bildirim", rating === 1 ? "Tesekkurler!" : "Geri bildiriminiz alindi.");
        } catch (error) {
            console.error("Feedback error:", error);
        }
    }

    return (
        <ScrollView style={styles.container}>
            {meta?.same_day && (
                <View style={styles.sameDayBanner}>
                    <Text style={styles.sameDayTitle}>Bugun kontrol onerisi</Text>
                    <Text style={styles.sameDayText}>{meta.same_day.message}</Text>
                </View>
            )}

            <Text style={styles.title}>Degerlendirme Sonucu</Text>

            {payload?.risk && (
                <View style={[styles.card, { borderColor: riskColor(payload.risk.level), backgroundColor: riskBg(payload.risk.level) }]}>
                    <Text style={[styles.sectionTitle, { color: riskColor(payload.risk.level) }]}>
                        Risk: {payload.risk.level} ({Math.round((payload.risk.score_0_1 ?? 0) * 100)}%)
                    </Text>
                    {(payload.risk.reasons ?? []).map((r: string, i: number) => (
                        <Text key={i} style={styles.riskReason}>
                            - {r}
                        </Text>
                    ))}
                    <Text style={styles.riskAdvice}>{payload.risk.advice}</Text>
                </View>
            )}

            <View style={styles.card}>
                <Text style={styles.label}>Onerilen Brans ID:</Text>
                <Text style={styles.value}>{payload.recommended_specialty_id ?? "-"}</Text>
            </View>

            <View style={styles.card}>
                <Text style={styles.label}>Guven:</Text>
                <Text style={styles.value}>
                    {(payload.confidence_0_1 * 100).toFixed(0)}%
                </Text>
            </View>

            <View style={styles.card}>
                <Text style={styles.label}>Durum sebebi:</Text>
                <Text style={styles.value}>{stop_reason ?? payload.stop_reason ?? "-"}</Text>
            </View>

            <View style={styles.card}>
                <Text style={styles.sectionTitle}>Muhtemel Durumlar</Text>
                {(payload.probable_conditions ?? []).map((c: any, idx: number) => (
                    <Text key={idx} style={styles.condition}>
                        - {c.name} ({(Number(c.score ?? 0) * 100).toFixed(0)}%)
                    </Text>
                ))}
            </View>

            <Text style={styles.feedbackTitle}>Bu sonuc yardimci oldu mu?</Text>
            <View style={styles.feedbackButtons}>
                <Button title="Evet" onPress={() => sendFeedback(1)} />
                <Button title="Hayir" onPress={() => sendFeedback(-1)} />
            </View>

            <View style={{ marginTop: 20 }}>
                <Button
                    title="Yeni Degerlendirme"
                    onPress={() => navigation.navigate("Home")}
                />
            </View>
        </ScrollView>
    );
}

const styles = StyleSheet.create({
    container: {
        padding: 16,
        backgroundColor: "#fff",
    },
    sameDayBanner: {
        padding: 12,
        borderRadius: 12,
        borderWidth: 1,
        borderColor: "#f59e0b",
        backgroundColor: "#fef3c7",
        marginBottom: 16,
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
    title: {
        fontSize: 24,
        fontWeight: "800",
        marginBottom: 16,
    },
    card: {
        padding: 12,
        borderRadius: 12,
        borderWidth: 1,
        borderColor: "#e5e7eb",
        marginBottom: 12,
    },
    label: {
        fontSize: 12,
        color: "#6b7280",
        marginBottom: 4,
    },
    value: {
        fontSize: 16,
        fontWeight: "600",
    },
    sectionTitle: {
        fontSize: 14,
        fontWeight: "700",
        marginBottom: 8,
    },
    condition: {
        fontSize: 14,
        marginBottom: 4,
    },
    riskReason: {
        fontSize: 13,
        opacity: 0.8,
        marginTop: 4,
    },
    riskAdvice: {
        fontSize: 13,
        marginTop: 8,
        opacity: 0.9,
    },
    feedbackTitle: {
        fontSize: 16,
        fontWeight: "600",
        marginTop: 16,
        marginBottom: 8,
    },
    feedbackButtons: {
        flexDirection: "row",
        gap: 10,
        justifyContent: "space-around",
    },
});
