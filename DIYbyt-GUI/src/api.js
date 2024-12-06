// api.js
const API_URL = `http://${window.location.hostname}:3001/api`;

export const listStarPrograms = async () => {
    const response = await fetch(`${API_URL}/programs`);
    return response.json();
};

export const saveStarProgram = async (name, content) => {
    const response = await fetch(`${API_URL}/programs`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ name, content }),
    });
    return response.json();
};

export const loadProgramMetadata = async () => {
    try {
        const response = await fetch(`${API_URL}/metadata`);
        const data = await response.json();
        
        // Ensure we have a valid object
        if (typeof data !== 'object' || data === null) {
            return {};
        }
        
        // Remove any empty keys
        delete data[""];
        
        // Ensure all entries have required fields
        const cleanedData = {};
        Object.entries(data).forEach(([key, value]) => {
            if (key && key.trim()) {  // Only process non-empty keys
                cleanedData[key] = {
                    config: {},
                    refresh_rate: 30,
                    order: value.order || 0,
                    enabled: value.enabled ?? true,
                    duration: value.duration || 30,
                    durationUnit: value.durationUnit || "seconds",
                    ...value
                };
            }
        });
        
        return cleanedData;
    } catch (error) {
        console.error('Error loading metadata:', error);
        return {};
    }
};

export const saveProgramMetadata = async (metadata) => {
    // Clean metadata before saving
    const cleanedMetadata = {};
    Object.entries(metadata).forEach(([key, value]) => {
        if (key && key.trim()) {  // Only save non-empty keys
            cleanedMetadata[key] = {
                config: value.config || {},
                refresh_rate: value.refresh_rate || 30,
                order: value.order || 0,
                enabled: value.enabled ?? true,
                duration: value.duration || 30,
                durationUnit: value.durationUnit || "seconds",
                ...value
            };
        }
    });

    const response = await fetch(`${API_URL}/metadata`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(cleanedMetadata),
    });
    return response.json();
};

export const deleteStarProgram = async (name) => {
    const response = await fetch(`${API_URL}/programs/${name}`, {
        method: 'DELETE'
    });
    return response.json();
};