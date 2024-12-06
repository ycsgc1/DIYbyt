import express from 'express';
import cors from 'cors';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { dirname } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const app = express();
const PORT = process.env.PORT || 3001;

// CORS configuration
app.use(cors({
    origin: true,
    credentials: true
}));

app.use(express.json());

// Serve static files from the dist directory
app.use(express.static(path.join(__dirname, '../dist')));

const STAR_PROGRAMS_DIR = path.join(__dirname, '../star_programs');

// Ensure directory exists
if (!fs.existsSync(STAR_PROGRAMS_DIR)) {
    fs.mkdirSync(STAR_PROGRAMS_DIR, { recursive: true });
}

// Ensure metadata file exists
const metadataPath = path.join(STAR_PROGRAMS_DIR, 'program_metadata.json');
if (!fs.existsSync(metadataPath)) {
    fs.writeFileSync(metadataPath, JSON.stringify({}, null, 2));
    console.log('Created empty metadata file');
}

// New endpoint: Get directory hash for sync checking
app.get('/api/sync/hash', (req, res) => {
    try {
        const crypto = require('crypto');
        const hash = crypto.createHash('sha256');
        
        // Get all files and sort them for consistent hashing
        const files = fs.readdirSync(STAR_PROGRAMS_DIR).sort();
        
        for (const file of files) {
            const filePath = path.join(STAR_PROGRAMS_DIR, file);
            const content = fs.readFileSync(filePath);
            hash.update(file);
            hash.update(content);
        }
        
        res.json({ hash: hash.digest('hex') });
    } catch (error) {
        res.status(500).json({ error: 'Failed to calculate directory hash' });
    }
});

// New endpoint: Get all programs and metadata for sync
app.get('/api/sync/all', (req, res) => {
    try {
        const files = fs.readdirSync(STAR_PROGRAMS_DIR);
        const data = {};
        
        for (const file of files) {
            const filePath = path.join(STAR_PROGRAMS_DIR, file);
            data[file] = fs.readFileSync(filePath, 'utf8');
        }
        
        res.json(data);
    } catch (error) {
        res.status(500).json({ error: 'Failed to get programs' });
    }
});

// Existing endpoints...
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

app.post('/api/programs', (req, res) => {
    try {
        const { name, content } = req.body;
        fs.writeFileSync(path.join(STAR_PROGRAMS_DIR, name), content);
        res.json({ success: true });
    } catch (error) {
        res.status(500).json({ error: 'Failed to save program' });
    }
});

app.get('/api/metadata', (req, res) => {
    try {
        const metadataPath = path.join(STAR_PROGRAMS_DIR, 'program_metadata.json');
        if (fs.existsSync(metadataPath)) {
            const metadata = JSON.parse(fs.readFileSync(metadataPath, 'utf8'));
            res.json(metadata);
        } else {
            fs.writeFileSync(metadataPath, JSON.stringify({}, null, 2));
            res.json({});
        }
    } catch (error) {
        console.error('Metadata error:', error);
        res.status(500).json({ error: 'Failed to load metadata' });
    }
});

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

// Catch-all route for serving the frontend
app.get('*', (req, res) => {
    res.sendFile(path.join(__dirname, '../dist/index.html'));
});

app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
});