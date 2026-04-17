import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useAuth } from "@/contexts/AuthContext";

const ProfileCompletion: React.FC = () => {
    const { user } = useAuth();
    const navigate = useNavigate();

    const [name, setName] = useState(user?.user_metadata?.name || user?.user_metadata?.full_name || "");
    const [phone, setPhone] = useState("");
    const [countryCode, setCountryCode] = useState("+1");
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState("");

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");

        // Validation
        if (!name.trim()) {
            setError("Please enter your name");
            return;
        }

        if (!phone.trim()) {
            setError("Please enter your phone number");
            return;
        }

        setIsLoading(true);

        try {
            if (!user) {
                setError("User not found. Please sign in again.");
                return;
            }

            // Update user metadata in Supabase
            const { supabase } = await import('@/lib/supabase');
            const { error: updateError } = await supabase.auth.updateUser({
                data: {
                    name: name,
                    phone: phone,
                    country_code: countryCode,
                }
            });

            if (updateError) {
                setError(updateError.message);
                setIsLoading(false);
                return;
            }

            // Update profile in backend using PUT endpoint
            const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';
            const accessToken = localStorage.getItem('accessToken');

            const response = await fetch(`${API_BASE_URL}/profiles/${user.id}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    ...(accessToken ? { 'Authorization': `Bearer ${accessToken}` } : {})
                },
                body: JSON.stringify({
                    auth_user_id: user.id,
                    email_id: user.email || '',
                    phone_number: phone,
                    name: name,
                    role: 'USER',
                    country_code: countryCode
                })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: 'Failed to update profile' }));
                setError(errorData.detail || errorData.message || 'Failed to update profile');
                setIsLoading(false);
                return;
            }

            // Success - redirect to home portal ('/' is now the public landing page)
            navigate('/home');
        } catch (err: any) {
            setError(err.message || "Failed to complete profile");
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="h-full overflow-y-auto flex justify-center py-12 px-4 sm:px-6 lg:px-8" style={{ backgroundColor: '#503b5d' }}>
            <div className="max-w-md w-full space-y-8">
                <Card>

                    <CardHeader>
                        <CardTitle className="text-2xl">Complete Your Profile</CardTitle>
                        <CardDescription>
                            Please provide additional information to complete your registration
                        </CardDescription>
                    </CardHeader>

                    <CardContent>
                        <form onSubmit={handleSubmit} className="space-y-4">
                            <div>
                                <Label htmlFor="name" className="text-gray-700">
                                    Full Name *
                                </Label>
                                <Input
                                    id="name"
                                    type="text"
                                    value={name}
                                    onChange={(e) => setName(e.target.value)}
                                    placeholder="John Doe"
                                    className="mt-1"
                                    disabled={isLoading}
                                    required
                                />
                            </div>

                            <div>
                                <Label htmlFor="phone" className="text-gray-700">
                                    Phone Number *
                                </Label>
                                <div className="flex gap-2 mt-1">
                                    <Select value={countryCode} onValueChange={setCountryCode}>
                                        <SelectTrigger className="w-[120px]">
                                            <SelectValue placeholder="Code" />
                                        </SelectTrigger>
                                        <SelectContent className="max-h-[200px] overflow-y-auto">
                                            <SelectItem value="+1">+1 (US)</SelectItem>
                                            <SelectItem value="+44">+44 (UK)</SelectItem>
                                            <SelectItem value="+91">+91 (IN)</SelectItem>
                                            <SelectItem value="+86">+86 (CN)</SelectItem>
                                            <SelectItem value="+81">+81 (JP)</SelectItem>
                                            <SelectItem value="+49">+49 (DE)</SelectItem>
                                            <SelectItem value="+33">+33 (FR)</SelectItem>
                                            <SelectItem value="+61">+61 (AU)</SelectItem>
                                            <SelectItem value="+971">+971 (AE)</SelectItem>
                                            <SelectItem value="+65">+65 (SG)</SelectItem>
                                        </SelectContent>
                                    </Select>
                                    <Input
                                        id="phone"
                                        type="tel"
                                        value={phone}
                                        onChange={(e) => setPhone(e.target.value)}
                                        placeholder="555 123 4567"
                                        className="flex-1"
                                        disabled={isLoading}
                                        required
                                    />
                                </div>
                            </div>

                            {error && (
                                <div className="p-3 bg-red-50 border border-red-200 rounded-md">
                                    <p className="text-red-600 text-sm">{error}</p>
                                </div>
                            )}

                            <Button
                                type="submit"
                                disabled={isLoading}
                                className="w-full bg-orange-600 hover:bg-orange-700 text-white"
                            >
                                {isLoading ? "Completing Profile..." : "Complete Profile"}
                            </Button>
                        </form>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
};

export default ProfileCompletion;
