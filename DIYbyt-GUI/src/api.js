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
    const response = await fetch(`${API_URL}/metadata`);
    return response.json();
};

export const saveProgramMetadata = async (metadata) => {
    const response = await fetch(`${API_URL}/metadata`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(metadata),
    });
    return response.json();
};

export const deleteStarProgram = async (name) => {
    const response = await fetch(`${API_URL}/programs/${name}`, {
        method: 'DELETE'
    });
    return response.json();
};