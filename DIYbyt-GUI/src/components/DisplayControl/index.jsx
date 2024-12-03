import { useState, useCallback } from 'react';
import { List, FileText, Plus, GripVertical, Edit2, X } from 'lucide-react';
import './styles.css';
import {
  validateStarFile,
  formatDuration,
  generateProgramId,
  reorderPrograms,
  saveProgramsToStorage,
  loadProgramsFromStorage
} from './utils';


const StarEditor = ({ isOpen, onClose, program, onSave }) => {
  const [content, setContent] = useState(program.content || '');

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center">
      <div className="bg-white rounded-lg w-3/4 max-w-4xl h-3/4 flex flex-col">
        <div className="p-4 border-b flex justify-between items-center">
          <h3 className="font-semibold">Editing {program.name}</h3>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-700">
            <X size={20} />
          </button>
        </div>
        
        <div className="flex-1 p-4">
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            className="w-full h-full font-mono text-sm border rounded p-2"
            spellCheck="false"
          />
        </div>
        
        <div className="p-4 border-t flex justify-end gap-2">
          <button 
            onClick={onClose}
            className="px-4 py-2 border rounded hover:bg-gray-50"
          >
            Cancel
          </button>
          <button 
            onClick={() => {
              onSave(program.id, content);
              onClose();
            }}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            Save Changes
          </button>
        </div>
      </div>
    </div>
  );
};

const DisplayControl = () => {
  const [programs, setPrograms] = useState([
    { 
      id: 1, 
      name: 'stars.star', 
      duration: 30, 
      durationUnit: 'seconds', 
      enabled: true,
      content: '// Your star program code here\n'
    },
    { 
      id: 2, 
      name: 'sparkle.star', 
      duration: 2, 
      durationUnit: 'loops', 
      enabled: true,
      content: '// Another star program\n'
    },
  ]);
  const [draggedItem, setDraggedItem] = useState(null);
  const [dragOverIndex, setDragOverIndex] = useState(null);
  const [editingProgram, setEditingProgram] = useState(null);

  const handleDragStart = (e, position) => {
    setDraggedItem(programs[position]);
    e.dataTransfer.effectAllowed = 'move';
    const dragGhost = document.createElement('div');
    dragGhost.style.display = 'none';
    document.body.appendChild(dragGhost);
    e.dataTransfer.setDragImage(dragGhost, 0, 0);
  };

  const handleDragOver = (e, position) => {
    e.preventDefault();
    setDragOverIndex(position);
    
    if (!draggedItem) return;
    
    const items = [...programs];
    const draggedOverItem = items[position];

    if (draggedItem === draggedOverItem) return;

    const newItems = items.filter(item => item.id !== draggedItem.id);
    newItems.splice(position, 0, draggedItem);

    setPrograms(newItems);
  };

  const handleDragEnd = () => {
    setDraggedItem(null);
    setDragOverIndex(null);
    // Clean up any ghost elements
    const ghostElements = document.querySelectorAll('div[style="display: none;"]');
    ghostElements.forEach(element => element.remove());
  };

  const handleFileUpload = useCallback((files) => {
    Array.from(files).forEach(file => {
      if (file.name.endsWith('.star')) {
        const reader = new FileReader();
        reader.onload = (e) => {
          const newProgram = {
            id: Date.now(),
            name: file.name,
            duration: 30,
            durationUnit: 'seconds',
            enabled: true,
            content: e.target.result
          };
          setPrograms(prev => [...prev, newProgram]);
        };
        reader.readAsText(file);
      } else {
        alert('Please upload only .star files');
      }
    });
  }, []);

  const handleDrop = (e) => {
    e.preventDefault();
    const files = e.dataTransfer.files;
    handleFileUpload(files);
  };

  const handleDurationChange = (id, value, unit) => {
    setPrograms(programs.map(program => {
      if (program.id === id) {
        return {
          ...program,
          duration: value,
          durationUnit: unit || program.durationUnit
        };
      }
      return program;
    }));
  };

  const handleSaveContent = (programId, newContent) => {
    setPrograms(programs.map(program => {
      if (program.id === programId) {
        return {
          ...program,
          content: newContent
        };
      }
      return program;
    }));
  };

  return (
    <div className="p-4 max-w-4xl mx-auto">
      <div className="mb-6 flex justify-between items-center">
        <h2 className="text-2xl font-bold">Display Programs</h2>
        <button className="bg-blue-500 text-white px-4 py-2 rounded-lg flex items-center gap-2 hover:bg-blue-600">
          <Plus size={20} /> Add Program
        </button>
      </div>

      <div className="bg-white rounded-lg shadow">
        <div className="p-4 border-b">
          <div className="flex items-center gap-2">
            <List size={20} />
            <h3 className="font-semibold">Program Queue</h3>
          </div>
        </div>
        
        <div className="divide-y">
          {programs.map((program, index) => (
            <div 
              key={program.id} 
              className={`p-4 flex items-center gap-4 hover:bg-gray-50 cursor-move transition-colors
                ${dragOverIndex === index ? 'border-t-2 border-blue-500' : ''}
                ${draggedItem?.id === program.id ? 'bg-gray-50 opacity-50' : ''}`}
              draggable
              onDragStart={(e) => handleDragStart(e, index)}
              onDragOver={(e) => handleDragOver(e, index)}
              onDragEnd={handleDragEnd}
            >
              <GripVertical size={20} className="text-gray-400" />
              
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <FileText size={16} className="text-gray-500" />
                  <span className="font-medium">{program.name}</span>
                  <button 
                    onClick={() => setEditingProgram(program)}
                    className="p-1 hover:bg-gray-100 rounded"
                  >
                    <Edit2 size={16} className="text-gray-500" />
                  </button>
                </div>
              </div>
              
              <div className="flex items-center gap-4">
                <div className="flex items-end gap-2">
                  <div>
                    <label className="block text-sm text-gray-500">Duration</label>
                    <input 
                      type="number" 
                      value={program.duration}
                      onChange={(e) => handleDurationChange(program.id, e.target.value)}
                      className="w-20 border rounded p-1"
                    />
                  </div>
                  <select 
                    value={program.durationUnit}
                    onChange={(e) => handleDurationChange(program.id, program.duration, e.target.value)}
                    className="border rounded p-1 h-8"
                  >
                    <option value="seconds">seconds</option>
                    <option value="loops">loops</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm text-gray-500">Enabled</label>
                  <input 
                    type="checkbox" 
                    checked={program.enabled}
                    className="w-4 h-4"
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div 
        className="mt-6 border-2 border-dashed rounded-lg p-8 text-center"
        onDrop={handleDrop}
        onDragOver={(e) => e.preventDefault()}
      >
        <div className="space-y-2">
          <p className="text-gray-500">Drag and drop .star files here</p>
          <p className="text-sm text-gray-400">or</p>
          <input
            type="file"
            id="file-upload"
            className="hidden"
            accept=".star"
            onChange={(e) => handleFileUpload(e.target.files)}
            multiple
          />
          <label htmlFor="file-upload" className="text-blue-500 hover:underline cursor-pointer">
            browse files
          </label>
        </div>
      </div>

      <StarEditor 
        isOpen={editingProgram !== null}
        onClose={() => setEditingProgram(null)}
        program={editingProgram || {}}
        onSave={handleSaveContent}
      />
    </div>
  );
};

export default DisplayControl;