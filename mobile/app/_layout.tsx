import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";

export default function RootLayout() {
  return (
    <>
      <StatusBar style="dark" />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: "#FAFAFA" },
          headerTintColor: "#111",
          headerTitleStyle: { fontWeight: "600", fontSize: 18 },
          headerShadowVisible: false,
          contentStyle: { backgroundColor: "#FAFAFA" },
        }}
      >
        <Stack.Screen
          name="index"
          options={{
            title: "Dotshub",
            headerShown: false,
          }}
        />
      </Stack>
    </>
  );
}
