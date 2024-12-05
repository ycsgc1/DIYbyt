import express from 'express';
import cors from 'cors';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { dirname } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const app = express();
const PORT = 3001;

app.use(cors());
app.use(express.json());

const STAR_PROGRAMS_DIR = './star_programs';

// Ensure directory exists
if (!fs.existsSync(STAR_PROGRAMS_DIR)) {
    fs.mkdirSync(STAR_PROGRAMS_DIR, { recursive: true });
}

// List all programs - single route handler
app.get('/api/programs', (req, res) => {
    try {
        const files = fs.readdirSync(STAR_PROGRAMS_DIR);
        const programs = files
            .filter(file => file.endsWith('.star'))
            .map(file => ({
                name: file,
                content: fs.readFileSync(path.join(STAR_PROGRAMS_DIR, file), 'utf8')
            }));
        res.json(programs);
    } catch (error) {
        res.status(500).json({ error: 'Failed to list programs' });
    }
});

// Save program
app.post('/api/programs', (req, res) => {
    try {
        const { name, content } = req.body;
        fs.writeFileSync(path.join(STAR_PROGRAMS_DIR, name), content);
        res.json({ success: true });
    } catch (error) {
        res.status(500).json({ error: 'Failed to save program' });
    }
});

// Get metadata
app.get('/api/metadata', (req, res) => {
    try {
        const metadataPath = path.join(STAR_PROGRAMS_DIR, 'program_metadata.json');
        if (fs.existsSync(metadataPath)) {
            const metadata = JSON.parse(fs.readFileSync(metadataPath, 'utf8'));
            res.json(metadata);
        } else {
            res.json({});
        }
    } catch (error) {
        res.status(500).json({ error: 'Failed to load metadata' });
    }
});

// Save metadata
app.post('/api/metadata', (req, res) => {
    try {
        const metadata = req.body;
        fs.writeFileSync(
            path.join(STAR_PROGRAMS_DIR, 'program_metadata.json'),
            JSON.stringify(metadata, null, 2)
        );
        res.json({ success: true });
    } catch (error) {
        res.status(500).json({ error: 'Failed to save metadata' });
    }
});

app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
});

app.delete('/api/programs/:name', (req, res) => {
    try {
        const fileName = req.params.name;
        const filePath = path.join(STAR_PROGRAMS_DIR, fileName);
        console.log('Attempting to delete:', filePath);
        fs.unlinkSync(filePath);
        
        // Also delete from metadata
        const metadataPath = path.join(STAR_PROGRAMS_DIR, 'program_metadata.json');
        if (fs.existsSync(metadataPath)) {
            const metadata = JSON.parse(fs.readFileSync(metadataPath, 'utf8'));
            delete metadata[fileName];
            fs.writeFileSync(metadataPath, JSON.stringify(metadata, null, 2));
        }
        
        console.log('Successfully deleted file and metadata');
        res.json({ success: true });
    } catch (error) {
        console.error('Delete error:', error);
        res.status(500).json({ error: `Failed to delete program: ${error.message}` });
    }
});