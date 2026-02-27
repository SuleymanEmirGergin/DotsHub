import { View, Text, Linking, Button, BackHandler, StyleSheet } from "react-native";
import { useEffect } from "react";

export default function EmergencyModal({ route }: any) {
    const { payload } = route.params;

    // Prevent back button
    useEffect(() => {
        const sub = BackHandler.addEventListener("hardwareBackPress", () => true);
        return () => sub.remove();
    }, []);

    return (
        <View style={styles.container}>
            <View style={styles.content}>
                <Text style={styles.title}>⚠️ ACİL DURUM</Text>
                <Text style={styles.message}>{payload.message}</Text>

                <View style={styles.actions}>
                    <Button
                        title="112'yi Ara"
                        onPress={() => Linking.openURL("tel:112")}
                        color="#dc2626"
                    />
                </View>

                <Text style={styles.disclaimer}>
                    Bu otomatik bir uyarıdır. Belirtileriniz acil müdahale gerektirebilir.
                </Text>
            </View>
        </View>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: "rgba(220, 38, 38, 0.95)",
        justifyContent: "center",
        alignItems: "center",
        padding: 20,
    },
    content: {
        backgroundColor: "#fff",
        borderRadius: 16,
        padding: 24,
        width: "100%",
        maxWidth: 400,
        shadowColor: "#000",
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.3,
        shadowRadius: 8,
        elevation: 8,
    },
    title: {
        fontSize: 28,
        fontWeight: "900",
        color: "#dc2626",
        marginBottom: 16,
        textAlign: "center",
    },
    message: {
        fontSize: 16,
        marginBottom: 24,
        textAlign: "center",
        lineHeight: 24,
    },
    actions: {
        marginBottom: 16,
    },
    disclaimer: {
        fontSize: 12,
        color: "#6b7280",
        textAlign: "center",
        fontStyle: "italic",
    },
});
